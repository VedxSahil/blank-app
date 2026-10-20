"""Verifier tests. All text below is a TEST FIXTURE written for the unit tests, not fund data."""

from pereport.chunker import Chunk
from pereport.verifier import (
    Computed,
    extract_facts,
    split_sentences,
    unsupported_facts,
    verify_answer,
)

EVIDENCE = (
    "As of 31 March 2024 Alpha Fund reported NAV of USD 1,250.5 million. "
    "TVPI was 1.8x and the management fee is 2%."
)


def _chunk(doc: str, page: int, text: str) -> Chunk:
    return Chunk(f"{doc}:p{page}:c0", doc, page, "S", None, None, "text", text)


def _keys(text: str, kind: str) -> set[str]:
    return {f.key for f in extract_facts(text) if f.kind == kind}


def test_extract_numbers_hand_worked() -> None:
    # 1,250.5 + "million" -> "1250.5mn"; 12.50% -> "12.5pct"; 1.8x -> "1.8x"; 2% -> "2pct"
    assert _keys("NAV USD 1,250.5 million, up 12.50%, TVPI 1.8x, fee 2%.", "number") == {
        "1250.5mn",
        "12.5pct",
        "1.8x",
        "2pct",
    }


def test_extract_dates_hand_worked() -> None:
    text = "On 31 March 2024, again March 31, 2024, in Q1 2024, FY25 and 2023."
    # day-month-year and month-day-year both canonicalise to 2024-03-31 (one key);
    # "Q1 2024" -> Q1-2024; "FY25" -> FY2025; bare year -> 2023.
    # The 31 and 2024 digits inside dates are not numbers.
    assert _keys(text, "date") == {"2024-03-31", "Q1-2024", "FY2025", "2023"}
    assert _keys(text, "number") == set()


def test_citation_markers_are_not_facts() -> None:
    assert extract_facts("It was reported [Doc Alpha, p.12].") == []


def test_entities_strip_leading_function_words_and_possessive() -> None:
    text = "The Alpha Fund's NAV rose. In Blackstone Group of Funds it fell."
    ents = {f.key for f in extract_facts(text)}
    assert ents == {"alpha fund", "nav", "blackstone group of funds"}


def test_unsupported_facts_number_date_entity() -> None:
    answer = "Alpha Fund reported NAV of 1,250.5 million on 31 March 2024, DPI 0.4x."
    missing = unsupported_facts(answer, EVIDENCE)
    # "1,250.5 million" in evidence as "USD 1,250.5 million" -> supported; date supported;
    # "0.4x" not in evidence; entity "DPI" not in evidence. Exactly those two.
    assert sorted(f.raw for f in missing) == ["0.4x", "DPI"]


def test_date_prefix_support() -> None:
    assert unsupported_facts("Reported in March 2024.", EVIDENCE) == []
    assert [f.raw for f in unsupported_facts("Reported in March 2023.", EVIDENCE)] == ["March 2023"]


def test_unit_must_match() -> None:
    assert [f.key for f in unsupported_facts("Fee is 2 percent-points of 2x.", "fee 2%")] != []
    # "2x" is not "2%": hand check
    assert [f.key for f in unsupported_facts("Return 2x.", "fee 2%") if f.kind == "number"] == [
        "2x"
    ]


def test_split_sentences_abbreviation_and_orphan_citation() -> None:
    text = "Mr. Rao is chair [D, p.1]. Fee is 2% [D, p.2]. [D, p.3] Next point [D, p.4]."
    assert split_sentences(text) == [
        "Mr. Rao is chair [D, p.1].",
        "Fee is 2% [D, p.2]. [D, p.3]",
        "Next point [D, p.4].",
    ]


def test_verify_keeps_supported_and_strips_unsupported() -> None:
    retrieved = [_chunk("doc", 3, EVIDENCE)]
    answer = (
        "NAV was USD 1,250.5 million as of 31 March 2024 [doc, p.3]. "  # supported
        "DPI was 0.4x [doc, p.3]. "  # 0.4x and DPI absent
        "The fee is 2% [doc, p.9]. "  # page 9 not retrieved
        "Fees are charged quarterly."  # no citation
    )
    res = verify_answer(answer, retrieved)
    assert res.kept == ["NAV was USD 1,250.5 million as of 31 March 2024 [doc, p.3]."]
    reasons = [r for s in res.stripped for r in s.reasons]
    assert "unsupported_number: 0.4x" in reasons
    assert "unsupported_entity: DPI" in reasons
    assert "citation_not_retrieved: [doc, p.9]" in reasons
    assert "no_citation" in reasons
    assert res.passed is False and res.refused is False
    assert res.unsupported_fact_count == 2


def test_verify_all_supported_passes() -> None:
    res = verify_answer("TVPI was 1.8x [doc, p.3].", [_chunk("doc", 3, EVIDENCE)])
    assert res.passed and not res.refused and res.unsupported_fact_count == 0


def test_verify_nothing_survives_means_refusal() -> None:
    res = verify_answer("The carry is 20% [doc, p.3].", [_chunk("doc", 3, EVIDENCE)])
    assert res.refused and res.text == ""


def test_calc_citation() -> None:
    # Hand-worked: computed TVPI = 1.8 -> written 1.8x has 1 decimal place; round(1.8, 1) == 1.8 OK.
    # Written 1.9x != 1.8 -> stripped.
    comp = {"tvpi": Computed(1.8, "TVPI total value to paid-in capital")}
    ok = verify_answer("TVPI is 1.8x [calc:tvpi].", [], comp)
    bad = verify_answer("TVPI is 1.9x [calc:tvpi].", [], comp)
    unknown = verify_answer("TVPI is 1.8x [calc:nope].", [], comp)
    assert ok.passed
    assert [r for s in bad.stripped for r in s.reasons] == ["unsupported_number: 1.9x"]
    assert [r for s in unknown.stripped for r in s.reasons] == ["unknown_calc: nope"]


def test_calc_rounding_to_written_precision() -> None:
    # computed 1.8333 written as 1.83x: round(1.8333, 2) = 1.83 OK; written 1.84x fails.
    comp = {"t": Computed(1.8333, "TVPI")}
    assert verify_answer("TVPI is 1.83x [calc:t].", [], comp).passed
    assert not verify_answer("TVPI is 1.84x [calc:t].", [], comp).passed


RATES = "The management fee is 2% of committed capital. Carry is 20% over an 8% hurdle."


def test_number_must_sit_next_to_the_same_words() -> None:
    # 20% IS in the chunk, but beside "carry", not "management fee".
    # Sentence anchors for 20%: {management, fee}. Evidence words within 5 of 20%: before it
    # {of, committed, capital, carry, is}, after it {over, an, hurdle}. No overlap -> unsupported.
    res = verify_answer("The management fee is 20% [doc, p.1].", [_chunk("doc", 1, RATES)])
    assert res.refused
    assert verify_answer("Carry is 20% [doc, p.1].", [_chunk("doc", 1, RATES)]).passed
    assert verify_answer("The management fee is 2% [doc, p.1].", [_chunk("doc", 1, RATES)]).passed


def test_spelled_out_numbers_are_checked() -> None:
    # "twenty" is absent from the evidence (it writes "20%"): stripped, not trusted.
    res = verify_answer("Carry is twenty percent [doc, p.1].", [_chunk("doc", 1, RATES)])
    assert res.refused
    assert [r for s in res.stripped for r in s.reasons] == ["unsupported_number: twenty"]
