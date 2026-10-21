"""Shared helpers for the PEReport portal pages."""
import json, os, time
import streamlit as st
import pe_engine as E

ROOT = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(ROOT, "docs", "sample", "Aurelian_Peak_Fund_Sample_PPM.pdf")
ILPA = os.path.join(ROOT, "data", "ILPA-Reporting-Template-v2.0.xlsx")
GOLD = os.path.join(ROOT, "eval", "gold_aurelian.json")
GOLD_ILPA = os.path.join(ROOT, "eval", "gold_ilpa.json")


def require_index() -> E.Index:
    idx = st.session_state.get("idx")
    if idx is None:
        st.info("Load a document in the sidebar (or tick the sample) to begin.")
        st.stop()
    return idx


def log_query(q: str, status: str, reason: str = "", hits=None):
    st.session_state.setdefault("log", []).append({
        "time": time.strftime("%H:%M:%S"), "question": q, "status": status, "reason": reason,
        "top section": hits[0]["section"] if hits else "", "top document": hits[0]["doc"] if hits else ""})


def run_validation(idx: E.Index, gold=None):
    if gold is None:   # pick the bundled set that matches the loaded documents
        path = GOLD_ILPA if all("ILPA" in d for d in idx.docs) else GOLD
        gold = json.load(open(path)) if os.path.exists(path) else None
    if gold is None:
        return None
    r = E.evaluate(idx, gold)
    st.session_state["val"] = r
    return r


def tile(col, label, value, help_=None):
    col.metric(label, value, help=help_)
