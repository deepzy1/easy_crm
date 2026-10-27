"""Run the fixture evaluation on TEST_DATABASE_URL and write honest measured evidence."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="easycrm-eval-") as directory:
        output = Path(directory) / "results.xml"
        result = subprocess.run(
            [
                str(ROOT / "backend/.venv/bin/python"),
                "-m",
                "pytest",
                "-q",
                "tests/test_evaluation.py",
                f"--junitxml={output}",
            ],
            cwd=ROOT / "backend",
        )
        if not output.exists():
            return result.returncode or 1
        tests = ElementTree.parse(output).findall(".//testcase")
        report = {
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "mode": "fixture_model_outputs_real_guardrails_and_postgresql",
            "live_inference": False,
            "cases": [
                {
                    "name": test.attrib["name"],
                    "duration_seconds": float(test.attrib.get("time", 0)),
                    "passed": test.find("failure") is None
                    and test.find("error") is None
                    and test.find("skipped") is None,
                }
                for test in tests
            ],
            "limitations": "Fixtures test extraction validation, grounding and escalation, not real model extraction accuracy or provider latency. Live outputs are nondeterministic and depend on saved workspace provider/model and credentials.",
        }
        destination = ROOT / "docs/evidence/session-5-evaluation.json"
        destination.write_text(json.dumps(report, indent=2) + "\n")
        print(f"Evaluation evidence: {destination}")
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
