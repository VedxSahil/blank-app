"""PEReport - Fund Document Assistant (Streamlit front end for pe_engine)."""
import json, os, tempfile, urllib.request
import streamlit as st
import pe_engine as E

SAMPLE = os.path.join(os.path.dirname(__file__), "docs", "sample", "Aurelian_Peak_Fund_Sample_PPM.pdf")
st.set_page_config(page_title="PEReport", page_icon="📄", layout="wide")
st.title("PEReport — Fund Document Assistant")
st.caption("Retrieval over fund documents with citations, refusals, verified fee arithmetic and a validation harness. "
           "Runs locally: no tokens are used unless you enable the optional AI mode.")


@st.cache_data(show_spinner=False)
def parse(name: str, data: bytes):
    suffix = ".pdf" if name.lower().endswith(".pdf") else ".txt"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data); path = f.name
    try:
        return E.load_document(path, name)
    finally:
        os.unlink(path)


with st.sidebar:
    st.header("1. Documents")
    files = st.file_uploader("Upload one or more PDF / text files", type=["pdf", "txt"], accept_multiple_files=True)
    use_sample = st.checkbox("Use the fictional sample (Aurelian Peak Fund PPM)", value=not files)
    st.header("2. Answer mode")
    mode = st.radio("Mode", ["Free report (offline, no tokens)", "AI answer (your Claude API key)"])
    key = st.text_input("Claude API key", type="password") if mode.startswith("AI") else ""

chunks = []
for f in files or []:
    chunks += parse(f.name, f.getvalue())
if use_sample and os.path.exists(SAMPLE):
    chunks += parse(os.path.basename(SAMPLE), open(SAMPLE, "rb").read())
if not chunks:
    st.info("Upload a document or tick the sample to begin."); st.stop()
idx = E.Index(chunks)
st.sidebar.success(f"{len(chunks)} passages from: {', '.join(idx.docs)}")
st.session_state.setdefault("refusals", 0)

tab_ask, tab_fee, tab_val = st.tabs(["Ask / Report", "Fee calculator", "Validation"])

with tab_ask:
    q = st.text_input("Question", "What are the management fee, performance fee and initial fee?")
    if st.button("Generate report", type="primary"):
        rep = E.draft_report(idx, q)
        if rep["refused"]:
            st.session_state.refusals += 1
            st.warning(f"**Not supported by the documents.** {E.MISSING}  \nReason: {rep['reason']}.  "
                       f"Refusals this session: {st.session_state.refusals}")
        elif mode.startswith("AI"):
            if not key:
                st.error("Enter your Claude API key in the sidebar, or switch to the free report.")
            else:
                ctx = "\n\n".join(f"[{i+1}] ({h['doc']}, {h['section']}, p.{h['page']}) {h['text']}"
                                  for i, h in enumerate(idx.hits_for(q)[:5]))
                body = {"model": "claude-haiku-5-5", "max_tokens": 700,
                        "system": ("You are a formal, conservative Investor Relations analyst. Answer ONLY from the passages. "
                                   "Format: 1) Executive Summary (3 sentences) 2) KPI table with Vintage, Commitments, DPI, RVPI, Net IRR "
                                   f"3) Portfolio Observations as bullets. Write '{E.MISSING}' for absent figures; never estimate. "
                                   "Cite every metric as [Source: file, section, p.N]."),
                        "messages": [{"role": "user", "content": f"PASSAGES:\n{ctx}\n\nQUESTION: {q}"}]}
                req = urllib.request.Request("https://api.anthropic.com/v1/messages", json.dumps(body).encode(),
                                             {"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
                try:
                    with urllib.request.urlopen(req, timeout=60) as r:
                        st.markdown("".join(b.get("text", "") for b in json.load(r)["content"]))
                except Exception as e:
                    st.error(f"API error: {e}")
        else:
            st.subheader("1. Executive Summary"); st.write(rep["summary"])
            st.subheader("2. Key Performance Indicators")
            st.table({"Metric": [k for k, _ in rep["kpis"]], "Value": [v for _, v in rep["kpis"]]})
            st.subheader("3. Extracted terms")
            for s, c in rep["terms"] or [(E.MISSING, None)]:
                st.markdown(f"- {s} {E.cite(c) if c else ''}")
            st.subheader("4. Portfolio / narrative observations")
            for s, c in rep["observations"]:
                st.markdown(f"- {s} {E.cite(c)}")

with tab_fee:
    c1, c2 = st.columns(2)
    amount = c1.number_input("Subscription (USD)", 0, 1_000_000_000, 1_500_000, step=50_000)
    growth = c2.number_input("Assumed NAV growth (%)", -100.0, 1000.0, 10.0) / 100
    cols = st.columns(len(idx.docs))
    for col, d in zip(cols, idx.docs):
        r = E.calc_fees(idx.chunks, d, amount, growth)
        col.markdown(f"**{d}**")
        for label, k in (("Initial fee", "initial"), ("Performance allocation", "performance"), ("Management fee / year", "management")):
            v = r[k]
            col.markdown(f"- {label}: " + (f"USD {v[0]:,.2f} ({v[1]}%) {v[2]}" if v else E.MISSING))
    st.caption("Computed in code from terms read out of each document. Hurdles and high-water marks are not modelled; verify against the source.")

with tab_val:
    st.write("Score the system on a fixed question set: `[{\"q\":..., \"answerable\":true, \"expect\":\"regex\"}, {\"q\":..., \"answerable\":false}]`.")
    g = st.file_uploader("Question set (JSON)", type=["json"], key="gold")
    gpath = os.path.join(os.path.dirname(__file__), "eval", "gold_aurelian.json")
    if not g and os.path.exists(gpath) and st.checkbox("Use the bundled Aurelian question set", value=True):
        gold = json.load(open(gpath))
    else:
        gold = json.load(g) if g else None
    if gold and st.button("Run validation"):
        r = E.evaluate(idx, gold)
        m = st.columns(4)
        m[0].metric("Accuracy", f"{r['accuracy']:.1%}")
        m[1].metric("Coverage (auto-answered correctly / all)", f"{r['coverage']:.1%}")
        m[2].metric("Refusals (correct / false)", f"{r['refusals']} ({r['correct_refusals']} / {r['false_refusals']})")
        m[3].metric("Unanswerable wrongly answered", f"{r['wrongly_answered']} / {r['unanswerable']}")
        st.dataframe([{"Question": x["q"], "Expected": "answer" if x["answerable"] else "refuse",
                       "Result": x["type"], "Reason": x["why"]} for x in r["rows"]], use_container_width=True)
