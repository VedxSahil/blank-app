"""Download every document listed in data/targets.json.

Usage: python scripts/download.py [data/targets.json]
Each target: {"url", "publisher", "filename", "notes"}. URLs must be real public documents the
user chose; this script never invents one. Failures are printed and exit status is 1.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pereport.fetch import pull


def main(argv: list[str]) -> int:
    targets_path = Path(argv[1] if len(argv) > 1 else "data/targets.json")
    targets = json.loads(targets_path.read_text())
    failures = [
        err
        for t in targets
        if (err := pull(t, Path("data/raw"), Path("data/manifest.json"), Path("sources.csv")))
    ]
    print(f"{len(targets) - len(failures)} of {len(targets)} downloaded")
    for f in failures:
        print("FAILED", f)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
