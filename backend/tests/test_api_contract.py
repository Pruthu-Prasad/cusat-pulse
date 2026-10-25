"""Every endpoint's status + JSON must match tests/golden.json (see tests/snapshot.py)."""
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def test_api_matches_golden():
    # Separate process: the snapshot swaps in a temp DB and stubs Gemma at import time.
    r = subprocess.run([sys.executable, "-m", "tests.snapshot", "check"], cwd=BACKEND,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    summary = [l for l in r.stdout.splitlines() if "identical" in l or l.startswith(("DIFF", "   was", "   now"))]
    assert r.returncode == 0, "\n".join(summary) or r.stderr[-2000:]
