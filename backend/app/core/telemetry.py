"""Callers pass only authored status codes, opaque IDs and numeric observations."""

import json
import logging


def record(event, **fields):
    logging.getLogger("easycrm").info(json.dumps({"event": event, **fields}))
