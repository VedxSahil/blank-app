"""Interface stub for A2 retrieval pipeline (B-A2): user original not found.

Intended role: user's earlier retrieval code. Until supplied, pereport.bm25 is the baseline.
"""

from typing import Any

from pereport._stub import blocked


def run_retrieval(*args: Any, **kwargs: Any) -> Any:
    """Placeholder for the A2 retrieval pipeline entry point. Signature is provisional."""
    blocked("A2 retrieval pipeline", "B-A2")
