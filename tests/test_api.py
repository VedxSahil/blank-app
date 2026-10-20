"""API tests with a TEST FIXTURE corpus."""

from fastapi.testclient import TestClient

from pereport.api import create_app
from pereport.chunker import Chunk

CHUNKS = [
    Chunk("fx:p1:c0", "fx", 1, "FEES", "2024-01-01", "F", "text", "The management fee is 2% of committed capital."),
    Chunk("fx:p2:c0", "fx", 2, "NAV", "2024-01-01", "F", "text", "The net asset value was 500 million at 30 June 2023."),
]  # fmt: skip


def _client(threshold: float | None = 0.2, chunks: list[Chunk] | None = None) -> TestClient:
    return TestClient(create_app(CHUNKS if chunks is None else chunks, threshold))


def test_ask_answer_and_refusal() -> None:
    c = _client()
    ok = c.post("/api/ask", json={"question": "What is the management fee?"}).json()
    assert not ok["refused"] and ok["verified"] is True
    assert ok["text"] == "The management fee is 2% of committed capital [fx, p.1]."
    assert [s["chunk_id"] for s in ok["sources"]] == ["fx:p1:c0"]
    no = c.post("/api/ask", json={"question": "What is the clawback?"}).json()
    assert no["refused"] and no["reason"] == "no_evidence" and no["sources"] == []


def test_uncalibrated_or_empty_returns_503_not_a_guess() -> None:
    assert _client(threshold=None).post("/api/ask", json={"question": "fee"}).status_code == 503
    assert _client(chunks=[]).post("/api/ask", json={"question": "fee"}).status_code == 503
    assert _client(threshold=None).get("/api/health").json() == {
        "ok": True, "chunks": 2, "calibrated": False, "banner": None,
    }  # fmt: skip


def test_empty_question_rejected() -> None:
    assert _client().post("/api/ask", json={"question": "  "}).status_code == 422


def test_report_chunk_documents_eval() -> None:
    c = _client()
    rep = c.post("/api/report").json()
    assert rep["total"] == 17 and 0 <= rep["disclosed"] <= rep["total"]
    flat = [ln for s in rep["sections"] for ln in s["lines"]]
    assert all(ln["chunk_ids"] for ln in flat if ln["disclosed"])
    assert all(
        ln["text"] == "Not disclosed in provided documents" for ln in flat if not ln["disclosed"]
    )
    assert c.get("/api/chunks/fx:p2:c0").json()["page"] == 2
    assert c.get("/api/chunks/nope").status_code == 404
    docs = c.get("/api/documents").json()["documents"]
    assert docs == [{"doc": "fx", "chunks": 2, "pages": 2, "date": "2024-01-01"}]
    assert c.get("/api/eval").json() == {"available": False}


def test_banner_is_reported_and_app_from_disk_reads_env(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from pereport.api import app_from_disk
    from pereport.store import save_chunks

    assert (
        TestClient(create_app(CHUNKS, 0.2, banner="SAMPLE")).get("/api/health").json()["banner"]
        == "SAMPLE"
    )
    save_chunks(tmp_path / "chunks" / "d.jsonl", CHUNKS)
    (tmp_path / "ev").mkdir()
    (tmp_path / "ev" / "gate.json").write_text('{"bm25": 0.2}')
    monkeypatch.setenv("PEREPORT_CHUNKS", str(tmp_path / "chunks"))
    monkeypatch.setenv("PEREPORT_EVAL", str(tmp_path / "ev"))
    monkeypatch.setenv("PEREPORT_BANNER", "FROM ENV")
    health = TestClient(app_from_disk()).get("/api/health").json()
    assert health == {"ok": True, "chunks": 2, "calibrated": True, "banner": "FROM ENV"}
