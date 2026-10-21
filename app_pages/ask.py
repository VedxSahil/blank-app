import json, urllib.request
import streamlit as st
import pe_engine as E
from portal import require_index, log_query

idx = require_index()
st.title("💬 Ask & report")
mode = st.radio("Answer mode", ["Free report (offline, no tokens)", "AI answer (your Claude API key)"], horizontal=True)
key = st.text_input("Claude API key", type="password") if mode.startswith("AI") else ""
q = st.text_input("Question", st.session_state.pop("prefill", "What are the management fee, performance fee and initial fee?"))

if st.button("Generate report", type="primary"):
    rep = E.draft_report(idx, q)
    if rep["refused"]:
        log_query(q, "refused", rep["reason"])
        st.warning(f"**Not supported by the documents.** {E.MISSING}  \nReason: {rep['reason']}.")
    elif mode.startswith("AI"):
        hits = [h for d in idx.docs for h in [x for x in idx.hits_for(q) if x["doc"] == d][:3]]
        log_query(q, "answered (AI)", "", hits)
        if not key:
            st.error("Enter your Claude API key, or switch to the free report.")
        else:
            ctx = "\n\n".join(f"[{i+1}] ({h['doc']}, {h['section']}, p.{h['page']}) {h['text']}" for i, h in enumerate(hits))
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
        log_query(q, "answered", "", [h for _, h in rep["observations"]])
        st.subheader("1. Executive Summary"); st.write(rep["summary"])
        st.subheader("2. Key Performance Indicators")
        st.table({"Metric": [k for k, _ in rep["kpis"]], "Value": [v for _, v in rep["kpis"]]})
        st.subheader("3. Extracted terms")
        for s, c in rep["terms"] or [(E.MISSING, None)]:
            st.markdown(f"- {s} {E.cite(c) if c else ''}")
        st.subheader("4. Portfolio / narrative observations")
        for s, c in rep["observations"]:
            st.markdown(f"- {s} {E.cite(c)}")
