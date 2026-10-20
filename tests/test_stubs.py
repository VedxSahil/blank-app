"""Stubs for unsupplied user modules must fail loudly, never return fake output."""

from collections.abc import Callable

import pytest

from pereport import (
    a1_extraction,
    a2_retrieval,
    a7_governance,
    a8_fund_admin,
    a9_dashboard,
)


@pytest.mark.parametrize(
    "fn",
    [
        a1_extraction.extract_structured,
        a2_retrieval.run_retrieval,
        a7_governance.load_governance_note,
        a8_fund_admin.run_fund_admin,
        a9_dashboard.build_dashboard,
    ],
)
def test_stub_raises_not_implemented(fn: Callable[[], object]) -> None:
    with pytest.raises(NotImplementedError, match=r"BLOCKERS\.md"):
        fn()
