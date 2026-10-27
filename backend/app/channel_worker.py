"""Run separately from the API: python -m app.channel_worker [--once]."""

import argparse
import asyncio
import logging

from app.services.channels import run_once


async def main(once):
    while True:
        try:
            await run_once()
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
