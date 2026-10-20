"""Download real documents and record provenance.

Every successful pull is appended to data/manifest.json (url, publisher, date, SHA-256, size,
local path) and to sources.csv. A failed pull is returned as an error string, never retried
and never replaced with other data.
"""

import csv
import hashlib
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

USER_AGENT = "PEReport-student-research/0.1 (non-commercial; contact: project owner)"


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download(url: str, dest: Path, timeout: float = 60.0) -> tuple[int, str]:
    """Fetch `url` into `dest`. Returns (bytes, content_type). Raises on any HTTP/URL error."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as out:
        ctype = resp.headers.get("Content-Type", "")
        total = 0
        for block in iter(lambda: resp.read(1 << 20), b""):
            out.write(block)
            total += len(block)
    return total, ctype


def pull(
    target: dict[str, str],
    raw_dir: Path,
    manifest_path: Path,
    sources_csv: Path,
    now: datetime | None = None,
) -> str | None:
    """Download one target (url, publisher, filename, notes). None on success, else the error."""
    dest = raw_dir / target["filename"]
    try:
        size, ctype = download(target["url"], dest)
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        dest.unlink(missing_ok=True)
        return f"{target['url']}: {type(e).__name__}: {e}"
    when = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    entry: dict[str, Any] = {
        "url": target["url"],
        "publisher": target["publisher"],
        "date_pulled": when,
        "local_path": str(dest),
        "sha256": sha256_file(dest),
        "bytes": size,
        "content_type": ctype,
    }
    manifest: list[dict[str, Any]] = []
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    manifest = [m for m in manifest if m["url"] != target["url"]] + [entry]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    new_file = not sources_csv.exists() or sources_csv.stat().st_size == 0
    with sources_csv.open("a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["url", "publisher", "date_pulled", "local_path", "notes"])
        w.writerow(
            [entry["url"], entry["publisher"], when, entry["local_path"], target.get("notes", "")]
        )
    return None
