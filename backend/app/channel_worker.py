"""Run separately from the API: python -m app.channel_worker [--once]."""

import argparse
import asyncio
import logging
import json
import time

from sqlalchemy.dialects.postgresql import insert
from app.core.database import SessionLocal
from app.models.entities import WorkerHeartbeat, now

from app.services.channels import run_once


async def main(once):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    while True:
        started = time.monotonic()
        try:
            await run_once()
            with SessionLocal() as db:
                db.execute(
                    insert(WorkerHeartbeat)
                    .values(name="channels", last_seen=now())
                    .on_conflict_do_update(index_elements=[WorkerHeartbeat.name], set_={"last_seen": now()})
                )
                db.commit()
            logging.getLogger("easycrm.channels").info(
                json.dumps(
                    {"event": "worker_tick", "duration_ms": round((time.monotonic() - started) * 1000)}
                )
            )
        except Exception:
            # Database/provider exceptions can contain parameters; never log traceback or payload.
            logging.getLogger("easycrm.channels").error("channel_worker_tick_failed")
            if once:
                raise SystemExit(1) from None
        if once:
            return
        await asyncio.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    asyncio.run(main(parser.parse_args().once))
