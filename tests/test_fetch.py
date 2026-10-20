"""Fetch tests against a local HTTP server serving TEST FIXTURE bytes."""

import csv
import functools
import hashlib
import http.server
import json
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pereport.fetch import pull, sha256_file

PAYLOAD = b"abc"
# SHA-256("abc") is the standard FIPS 180-2 test vector:
ABC_SHA = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


@pytest.fixture
def server(tmp_path: Path) -> Iterator[str]:
    (tmp_path / "served").mkdir()
    (tmp_path / "served" / "doc.pdf").write_bytes(PAYLOAD)
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(tmp_path / "served")
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_sha256_known_vector(tmp_path: Path) -> None:
    f = tmp_path / "x"
    f.write_bytes(PAYLOAD)
    assert sha256_file(f) == ABC_SHA == hashlib.sha256(PAYLOAD).hexdigest()


def test_pull_records_manifest_and_sources(server: str, tmp_path: Path) -> None:
    target = {
        "url": f"{server}/doc.pdf",
        "publisher": "Fixture Publisher",
        "filename": "doc.pdf",
        "notes": "fixture",
    }
    manifest, sources = tmp_path / "m.json", tmp_path / "s.csv"
    when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert pull(target, tmp_path / "raw", manifest, sources, now=when) is None
    entry = json.loads(manifest.read_text())[0]
    assert entry["sha256"] == ABC_SHA and entry["bytes"] == 3
    assert entry["date_pulled"] == "2026-01-02T03:04:05+00:00"
    assert (tmp_path / "raw" / "doc.pdf").read_bytes() == PAYLOAD
    rows = list(csv.reader(sources.open()))
    assert rows[0] == ["url", "publisher", "date_pulled", "local_path", "notes"]
    assert rows[1][0] == target["url"] and rows[1][4] == "fixture"
    # pulling again replaces the manifest entry instead of duplicating it
    pull(target, tmp_path / "raw", manifest, sources, now=when)
    assert len(json.loads(manifest.read_text())) == 1


def test_failed_pull_returns_error_and_leaves_nothing(server: str, tmp_path: Path) -> None:
    target = {"url": f"{server}/missing.pdf", "publisher": "p", "filename": "m.pdf"}
    err = pull(target, tmp_path / "raw", tmp_path / "m.json", tmp_path / "s.csv")
    assert err is not None and "404" in err
    assert not (tmp_path / "raw" / "m.pdf").exists()
    assert not (tmp_path / "m.json").exists() and not (tmp_path / "s.csv").exists()
