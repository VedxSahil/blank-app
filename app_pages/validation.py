import json
import streamlit as st
import pe_engine as E
from portal import require_index, run_validation, GOLD, GOLD_ILPA
import os

idx = require_index()
st.title("✅ Validation")
st.write('Score the system on a fixed question set: `[{"q":..., "answerable":true, "expect":"regex"}, {"q":..., "answerable":false}]`.')
g = st.file_uploader("Question set (JSON)", type=["json"])
sets = {"Aurelian Peak PPM (37 questions)": GOLD, "ILPA template (28 questions)": GOLD_ILPA}
default = 1 if all("ILPA" in d for d in idx.docs) else 0
choice = st.selectbox("Bundled question set (match it to the loaded document)", list(sets), index=default, disabled=bool(g))
if st.button("Run validation", type="primary"):
    gold = json.load(g) if g else json.load(open(sets[choice]))
    if gold: run_validation(idx, gold)
r = st.session_state.get("val")
if r:
    m = st.columns(4)
    m[0].metric("Accuracy", f"{r['accuracy']:.1%}")
    m[1].metric("Coverage", f"{r['coverage']:.1%}", help="Answered correctly and automatically / all questions")
    m[2].metric("Refusals", f"{r['refusals']}", f"{r['correct_refusals']} correct / {r['false_refusals']} false", delta_color="off")
    m[3].metric("Unanswerable wrongly answered", f"{r['wrongly_answered']} / {r['unanswerable']}")
    st.dataframe([{"Question": x["q"], "Expected": "answer" if x["answerable"] else "refuse",
                   "Result": x["type"], "Reason": x["why"]} for x in r["rows"]], hide_index=True)
