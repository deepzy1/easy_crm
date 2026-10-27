"""Bounded, review-first ingestion. Originals are discarded after extraction.

No crawling, scripts, cookies, proxy environment, attachments or model tools.
HTTPS sockets are pinned to a vetted DNS answer, retaining hostname TLS validation.
"""

import http.client
import ipaddress
import re
import socket
import ssl
import subprocess
import tempfile
import time
import sys
import shutil
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 2 * 1024 * 1024
MAX_TEXT = 12000


class IngestionError(Exception):
    pass


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self.hidden += 1
        elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "section", "tr"} and not self.hidden:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def clean_text(value):
    value = value.replace("\x00", "")
    value = re.sub(r"[^\S\n]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n\n", value).strip()
    if not value:
        raise IngestionError("No readable text found. Scanned PDFs need OCR before upload.")
    if len(value) > MAX_TEXT:
        raise IngestionError(
            "Extracted text exceeds 12,000 characters. Split this source into smaller documents."
        )
    return value


def public_target(url):
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
            or parsed.query
            or parsed.fragment
            or len(url) > 500
            or not parsed.hostname.isascii()
        ):
            raise ValueError
        answers = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(a[4][0] for a in answers))
        if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
            raise ValueError
    except (ValueError, OSError):
        raise IngestionError(
            "Use a public HTTPS URL on port 443 without credentials, query parameters or fragments."
        ) from None
    return parsed, addresses[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname, address):
        super().__init__(hostname, timeout=8, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # A numeric address prevents a second DNS lookup from rebinding to an internal host.
        sock = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def fetch_page(url):
    for _ in range(3):
        parsed, address = public_target(url)
        connection = PinnedHTTPS(parsed.hostname, address)
        response = None
        try:
            connection.request(
                "GET",
                parsed.path or "/",
                headers={
                    "User-Agent": "EasyCRM-Knowledge/1.0",
                    "Accept": "text/html,text/plain",
                    "Accept-Encoding": "identity",
                },
            )
            # getresponse() detaches connection.sock for Connection: close replies;
            # the response's file keeps the transport alive until it is consumed.
            transport = connection.sock
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location", "")
                if not location:
                    raise IngestionError("Website returned a redirect without a destination.")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise IngestionError("Website did not return a readable public page (HTTP 200 required).")
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
            if (
                content_type not in {"text/html", "text/plain"}
                or response.getheader("Content-Encoding", "identity") != "identity"
            ):
                raise IngestionError("Only uncompressed HTML or plain-text pages are supported.")
            deadline = time.monotonic() + 8
            chunks, size = [], 0
            while size <= MAX_BYTES:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise IngestionError("Website download exceeded the time limit.")
                transport.settimeout(remaining)
                chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if response.isclosed():
                    break
            raw = b"".join(chunks)
            if len(raw) > MAX_BYTES:
                raise IngestionError("Website exceeds the 2 MiB download limit.")
            if content_type == "text/plain":
                return clean_text(raw.decode("utf-8", errors="replace"))
            parser = VisibleText()
            parser.feed(raw.decode("utf-8", errors="replace"))
            return clean_text("".join(parser.parts))
        except (OSError, http.client.HTTPException, UnicodeError):
            raise IngestionError(
                "Website connection failed or timed out. Check public HTTPS access."
            ) from None
        finally:
            if response is not None:
                response.close()
            connection.close()
    raise IngestionError("Website redirected too many times; use the final public page URL.")


def extract_pdf(raw):
    if not raw.startswith(b"%PDF-") or len(raw) > MAX_BYTES:
        raise IngestionError("Upload a PDF file of at most 2 MiB.")
    try:
        if not shutil.which("pdftotext"):
            raise FileNotFoundError
        # Files live in a private temporary directory and are removed on every outcome.
        # Poppler runs unprivileged in the deployment container, with a time/output bound.
        with tempfile.TemporaryDirectory(prefix="easycrm-pdf-") as directory:
            source, target = Path(directory) / "source.pdf", Path(directory) / "text.txt"
            source.write_bytes(raw)
            subprocess.run(
                [sys.executable, str(Path(__file__).parents[1] / "pdf_extract.py"), str(source), str(target)],
                timeout=10,
                check=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with target.open("rb") as output:
                text = output.read(MAX_TEXT * 4 + 1)
            if len(text) > MAX_TEXT * 4:
                raise IngestionError("PDF text is too large. Split it into smaller documents.")
            return clean_text(text.decode("utf-8"))
    except FileNotFoundError:
        raise IngestionError(
            "PDF extraction unavailable. Install poppler-utils on the backend host."
        ) from None
    except (subprocess.SubprocessError, OSError, UnicodeError):
        raise IngestionError(
            "PDF cannot be read, is encrypted or took too long. Upload a text PDF."
        ) from None
