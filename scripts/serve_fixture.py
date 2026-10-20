"""Serve the API over a tiny INVENTED fixture corpus, for the Playwright end-to-end test only.

The text below is not fund data and must never be used in the evaluation, viva or any report.
Usage: python scripts/serve_fixture.py [port]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402

from pereport.api import create_app  # noqa: E402
from pereport.chunker import Chunk  # noqa: E402

FIXTURE = [
    ("p1", 1, "FEES", "The management fee is 2% of committed capital."),
    ("p1", 1, "CARRY", "Carried interest is 20% over an 8% hurdle rate."),
    ("p2", 2, "NAV", "The net asset value of the fund was 500 million at 30 June 2023."),
    ("p3", 3, "AUDIT", "The auditor of the fund is Beta Audit LLP."),
]
CHUNKS = [
    Chunk(f"fixture:p{page}:c{i}", "fixture-doc", page, sec, "2024-01-01", "Fixture Fund", "text", text)
    for i, (_, page, sec, text) in enumerate(FIXTURE)
]

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run(create_app(CHUNKS, threshold=0.5), host="127.0.0.1", port=port, log_level="warning")
