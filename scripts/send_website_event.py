#!/usr/bin/env python3
"""Trusted-server sample: sign an exact JSON file and deliver it to EasyCRM.

Keep EASYCRM_WEBHOOK_SECRET server-side. No secret is printed or accepted in arguments.
"""

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request


def signed_headers(secret, event_id, raw, timestamp=None):
    stamp = str(int(time.time()) if timestamp is None else timestamp)
    digest = hmac.new(
        secret.encode(),
        stamp.encode() + b"." + event_id.encode() + b"." + raw,
        hashlib.sha256,
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-EasyCRM-Event-ID": event_id,
        "X-EasyCRM-Timestamp": stamp,
        "X-EasyCRM-Signature": "sha256=" + digest,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Full generated webhook URL")
    parser.add_argument(
        "--event-id", required=True, help="Stable ID; reuse on redelivery"
    )
    parser.add_argument("--body-file", type=Path, required=True)
    args = parser.parse_args()
    secret = os.environ.get("EASYCRM_WEBHOOK_SECRET", "")
    if not secret:
        parser.error("Set EASYCRM_WEBHOOK_SECRET on the trusted backend")
    raw = args.body_file.read_bytes()
    json.loads(raw)
    request = urllib.request.Request(
        args.url,
        data=raw,
        headers=signed_headers(secret, args.event_id, raw),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(response.status, response.read().decode())
    except urllib.error.HTTPError as exc:
        print(exc.code, "Webhook rejected; check the workspace delivery log")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
