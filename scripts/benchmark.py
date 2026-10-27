"""Serial in-process API benchmark. Disposable database only; no provider calls."""

import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
test_url = os.environ.get("TEST_DATABASE_URL", "")
if not test_url.split("?")[0].endswith("_test"):
    raise SystemExit("Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test")
os.environ["DATABASE_URL"] = test_url
os.environ["GEMINI_API_KEY"] = ""
os.environ["NVIDIA_API_KEY"] = ""
os.environ["WEBHOOK_MASTER_KEY"] = "fictional-benchmark-key-do-not-use-in-deployment"
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402
from app.main import app  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.entities import User, Workspace  # noqa: E402


def measure(call):
    values = []
    for i in range(30):
        start = time.perf_counter()
        response = call(i)
        elapsed = (time.perf_counter() - start) * 1000
        if response.status_code not in (200, 202):
            raise SystemExit(f"Benchmark failed: HTTP {response.status_code}")
        values.append(elapsed)
    return {
        "samples": len(values),
        "mean_ms": round(statistics.mean(values), 2),
        "p95_ms": round(sorted(values)[28], 2),
        "serial_requests_per_second": round(1000 / statistics.mean(values), 2),
    }


def main():
    email = f"benchmark-{uuid4().hex}@example.com"
    with TestClient(app, headers={"Origin": "http://localhost:5173"}) as client:
        result = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "name": "Fictional benchmark",
                "workspace_name": "Fictional benchmark",
                "password": "Fictional-benchmark-password!",
            },
        )
        if result.status_code != 201:
            raise SystemExit("Benchmark registration failed; check migrations and limits")
        user = result.json()["user"]["id"]
        ws = client.get("/api/v1/auth/me").json()["workspaces"][0]["id"]
        base = f"/api/v1/workspaces/{ws}"
        try:
            client.post(base + "/leads", json={"name": "Fictional benchmark lead"}).raise_for_status()
            integration = client.post(
                base + "/integrations", json={"name": "Benchmark", "kind": "website"}
            ).json()
            reads = measure(lambda _: client.get(base + "/leads"))

            def webhook(i):
                stamp, event = str(int(time.time())), f"benchmark-{i}"
                raw = json.dumps(
                    {"lead": {"name": "Fictional test", "email": "benchmark@example.com", "message": "Hello"}}
                ).encode()
                signature = (
                    "sha256="
                    + hmac.new(
                        integration["signing_secret"].encode(),
                        stamp.encode() + b"." + event.encode() + b"." + raw,
                        hashlib.sha256,
                    ).hexdigest()
                )
                return client.post(
                    integration["webhook_url"],
                    content=raw,
                    headers={
                        "Content-Type": "application/json",
                        "X-EasyCRM-Timestamp": stamp,
                        "X-EasyCRM-Event-ID": event,
                        "X-EasyCRM-Signature": signature,
                    },
                )

            intake = measure(webhook)
            report = {
                "mode": "serial_in_process_testclient_real_postgresql",
                "python": platform.python_version(),
                "crud_list": reads,
                "signed_webhook_acceptance": intake,
                "inference": "not executed",
                "limitations": "30 sequential requests per operation, one workspace and one lead, warm local database. Excludes TCP, TLS, proxy, concurrency, AI and external delivery. Not production throughput.",
            }
            destination = ROOT / "docs/evidence/session-5-benchmark.json"
            destination.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
        finally:
            with SessionLocal() as db:
                db.execute(delete(Workspace).where(Workspace.id == ws))
                db.execute(delete(User).where(User.id == user))
                db.commit()


if __name__ == "__main__":
    main()
