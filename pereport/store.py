"""Chunk store: one JSON object per line."""

import json
from dataclasses import asdict
from pathlib import Path

from pereport.chunker import Chunk


def save_chunks(path: str | Path, chunks: list[Chunk]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")


def load_chunks(path: str | Path) -> list[Chunk]:
    with Path(path).open(encoding="utf-8") as f:
        return [Chunk(**json.loads(line)) for line in f if line.strip()]
