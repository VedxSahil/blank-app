import json
import streamlit as st
import pe_engine as E
from portal import require_index, run_validation, GOLD
import os

idx = require_index()
st.title("✅ Validation")
st.write('Score the system on a fixed question set: `[{"q":..., "answerable":true, "expect":"regex"}, {"q":..., "answerable":false}]`.')
g = st.file_uploader("Question set (JSON)", type=["json"])
bundled = os.path.exists(GOLD) and st.checkbox("Use the bundled Aurelian question set", value=not g)
if st.button("Run validation", type="primary"):
    gold = json.load(g) if g else (json.load(open(GOLD)) if bundled else None)
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
