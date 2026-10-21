import streamlit as st
from portal import SAMPLE

st.title("PEReport — Fund Document Assistant")
st.markdown(
    "Ask questions about private-fund documents and get **cited answers**, **refusals** when the documents "
    "do not support an answer, **fee arithmetic computed in code**, and a validation score. "
    "Everything runs locally; no tokens are used unless you switch on the optional AI mode.")

c = st.columns(4)
c[0].page_link("app_pages/ask.py", label="Ask & report", icon="💬")
c[1].page_link("app_pages/fees.py", label="Fee calculator", icon="🧮")
c[2].page_link("app_pages/dashboard.py", label="Dashboard", icon="📊")
c[3].page_link("app_pages/validation.py", label="Validation", icon="✅")

st.subheader("How it works")
a, b, d = st.columns(3)
a.markdown("**1. Load**  \nUpload PDFs or use the fictional sample. Text is cleaned and split into passages tagged by document, section and page.")
b.markdown("**2. Retrieve & check**  \nBM25 ranking finds the best passages. A refusal rule declines questions the documents cannot support.")
d.markdown("**3. Report**  \nExecutive summary, KPI table and observations, every figure cited; missing figures are marked, never estimated.")

st.subheader("Try a question")
samples = ["What are the management fee, performance fee and initial fee?", "What is the redemption notice period and gate?",
           "What is the Zandrian tax rate on net income?", "What is the fund's net IRR?  (expect a refusal)"]
cols = st.columns(len(samples))
for col, s in zip(cols, samples):
    if col.button(s):
        st.session_state["prefill"] = s.split("  (")[0]
        st.switch_page("app_pages/ask.py")

idx = st.session_state.get("idx")
st.subheader("Status")
if idx:
    st.success(f"{len(idx.chunks)} passages loaded from: {', '.join(idx.docs)}")
else:
    st.warning("No document loaded. Use the sidebar.")
st.caption("Outputs are research aids. Verify every figure against the cited page before relying on it.")
