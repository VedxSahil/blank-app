"""Engine tests. Corpus and generators are TEST FIXTURES (invented text)."""

from pereport.chunker import Chunk
from pereport.engine import REFUSAL_TEXT, Engine, ExtractiveGenerator
from pereport.gate import Gate
from pereport.retrieval import HybridRetriever


def _c(page: int, text: str, kind: str = "text") -> Chunk:
    return Chunk(f"fx:p{page}:c0", "fx", page, "S", None, None, kind, text)


CORPUS = [
    _c(1, "The management fee is 2% of committed capital. Carry is 20% over an 8% hurdle."),
    _c(2, "NAV was 500 million at 30 June 2023. The auditor is Beta Audit LLP."),
    _c(3, "Year  Called  Paid\n2021  100  40", kind="table"),
]


def _engine(**kw: object) -> Engine:
    return Engine(HybridRetriever(CORPUS), Gate(0.5), **kw)  # type: ignore[arg-type]


class BadGenerator:
    def generate(self, question: str, chunks: list[Chunk]) -> str:
        return "The management fee is 5% [fx, p.1]. Carry is 20% [fx, p.1]."


def test_answer_is_extractive_cited_and_verified() -> None:
    a = _engine().ask("What is the management fee?")
    assert not a.refused and a.reason == "answered"
    assert a.text == "The management fee is 2% of committed capital [fx, p.1]."
    assert a.verification is not None and a.verification.passed
    assert [c.chunk_id for c in a.sources] == ["fx:p1:c0"]
    assert a.cited_pages == {("fx", 1)}


def test_table_row_answer() -> None:
    a = _engine().ask("Called Paid 2021")
    # data row (overlap 3 with header words) beats the header row alone (overlap 2)
    assert a.text == "Year  Called  Paid / 2021  100  40 [fx, p.3]."
    assert a.verification is not None and a.verification.passed


def test_unsupported_question_is_refused_with_standard_text() -> None:
    a = _engine().ask("What is the waterfall catch-up rate?")
    assert a.refused and a.text == REFUSAL_TEXT and a.reason == "no_evidence"


def test_low_score_is_refused() -> None:
    a = Engine(HybridRetriever(CORPUS), Gate(99.0)).ask("What is the management fee?")
    assert a.refused and a.reason == "low_score"


def test_verifier_strips_bad_generator_output() -> None:
    a = _engine(generator=BadGenerator()).ask("What is the management fee?")
    # gate's key-fact check sees the unsupported "5%" and refuses the whole draft
    assert a.refused and a.reason == "unsupported_facts" and a.draft_unsupported == 1


def test_verifier_alone_keeps_only_supported_sentence() -> None:
    a = _engine(generator=BadGenerator(), use_gate=False).ask("What is the management fee?")
    assert not a.refused
    assert a.text == "Carry is 20% [fx, p.1]."
    assert a.draft_unsupported == 1


def test_ablation_no_gate_no_verifier_lets_hallucination_through() -> None:
    a = _engine(generator=BadGenerator(), use_gate=False, use_verifier=False).ask(
        "What is the management fee?"
    )
    assert not a.refused and "5%" in a.text  # visible in ablation
    assert a.draft_unsupported == 1  # and counted, so the eval can measure it


def test_extractive_generator_needs_overlap() -> None:
    assert ExtractiveGenerator().generate("unrelated waterfall", CORPUS) == ""
    assert ExtractiveGenerator().generate("the of", CORPUS) == ""


def test_acronym_asked_but_absent_is_refused_not_answered_with_a_neighbour() -> None:
    # Corpus mentions "net" and "fund" but never IRR. Without the mandatory-term rule the NAV
    # sentence would answer an IRR question.
    corpus = [_c(2, "The net asset value of the fund was 500 million at 30 June 2023.")]
    eng = Engine(HybridRetriever(corpus), Gate(0.5))
    a = eng.ask("What is the net IRR of the fund?")
    assert a.refused and a.reason == "key_term_missing"


def test_glossary_expansion_lets_nav_match_spelled_out_text() -> None:
    corpus = [_c(2, "The net asset value of the fund was 500 million at 30 June 2023.")]
    a = Engine(HybridRetriever(corpus), Gate(0.5)).ask("What is the NAV?")
    assert not a.refused and a.text.endswith("[fx, p.2].")


def test_year_in_question_must_appear_in_answer() -> None:
    corpus = [_c(2, "Distributions were 40 million in 2022.")]
    eng = Engine(HybridRetriever(corpus), Gate(0.5))
    assert eng.ask("What were distributions in 2022?").reason == "answered"
    # 2021 is absent from the corpus. The extractive generator already declines (too little overlap);
    # a generator that always answers shows the mandatory-term rule catching it independently.
    assert eng.ask("What were distributions in 2021?").refused

    class Always:
        def generate(self, question: str, chunks: list[Chunk]) -> str:
            return "Distributions were 40 million in 2022 [fx, p.2]."

    forced = Engine(HybridRetriever(corpus), Gate(0.0), generator=Always())
    assert forced.ask("What were distributions in 2021?").reason == "key_term_missing"
