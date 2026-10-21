import pandas as pd
import streamlit as st
import pe_engine as E
from portal import require_index, run_validation

idx = require_index()
st.title("📊 Dashboard")

if "val" not in st.session_state:
    run_validation(idx)          # bundled question set, if present
val, log = st.session_state.get("val"), st.session_state.get("log", [])
df = pd.DataFrame(idx.chunks)

# --- headline tiles
t = st.columns(6)
t[0].metric("Documents", len(idx.docs))
t[1].metric("Passages", len(idx.chunks))
t[2].metric("Sections found", df["section"].nunique())
t[3].metric("Queries this session", len(log))
t[4].metric("Refusals this session", sum(1 for x in log if x["status"] == "refused"))
t[5].metric("Validation accuracy", f"{val['accuracy']:.1%}" if val else "n/a")

left, right = st.columns(2)
with left:
    st.subheader("Passages per section")
    order = list(dict.fromkeys(df["section"]))
    sec = df.groupby(["section", "doc"]).size().unstack(fill_value=0).reindex(order)
    st.bar_chart(sec, horizontal=True)
with right:
    st.subheader("Validation outcomes")
    if val:
        counts = pd.Series([r["type"] for r in val["rows"]]).value_counts()
        st.bar_chart(counts)
        c = st.columns(3)
        c[0].metric("Coverage", f"{val['coverage']:.1%}")
        c[1].metric("Answerable correct", f"{val['answerable_correct']:.1%}")
        c[2].metric("Correct refusals", f"{val['correct_refusals']}/{val['unanswerable']}")
    else:
        st.info("No question set found. Run one on the Validation page.")

fm = E.fund_metrics(idx.chunks)
if "dpi" in fm:
    st.subheader("Fund metrics (computed from the capital account, LP allocation, inception to date)")
    m = st.columns(6)
    m[0].metric("Paid-in capital", f"{fm['paid_in']/1e6:,.1f}M"); m[1].metric("Distributions", f"{fm['distributions']/1e6:,.1f}M")
    m[2].metric("Ending NAV", f"{fm['nav']/1e6:,.1f}M"); m[3].metric("DPI", f"{fm['dpi']:.2f}x")
    m[4].metric("RVPI", f"{fm['rvpi']:.2f}x"); m[5].metric("TVPI", f"{fm['tvpi']:.2f}x")
    st.caption("DPI = distributions / paid-in; RVPI = ending NAV (net of carry) / paid-in; TVPI = DPI + RVPI. Net IRR needs dated cash flows, which the template does not contain.")
st.subheader("Quarterly-metric availability")
rows = []
for d in idx.docs:
    k = dict(E.kpi_table([c for c in idx.chunks if c["doc"] == d]))
    rows.append({"Document": d, **{m: ("found" if v != E.MISSING else "missing") for m, v in k.items()}})
st.dataframe(pd.DataFrame(rows), hide_index=True)
st.caption("A metric counts as found only if the document states it with a number. Offering memoranda normally do not contain DPI, RVPI or Net IRR.")

st.subheader("Fees by document")
amt = st.number_input("Subscription for comparison (USD)", 0, 1_000_000_000, 1_500_000, step=50_000, key="dash_amt")
fr = []
for d in idx.docs:
    r = E.calc_fees(idx.chunks, d, amt, 0.10)
    f = lambda v: f"{v[0]:,.0f} ({v[1]}%)" if v else "missing"
    fr.append({"Document": d, "Initial fee": f(r["initial"]), "Performance (10% growth)": f(r["performance"]), "Management / yr": f(r["management"])})
st.dataframe(pd.DataFrame(fr), hide_index=True)

st.subheader("Query log")
if log:
    ldf = pd.DataFrame(log)
    a, b = st.columns([2, 1])
    a.dataframe(ldf, hide_index=True)
    b.write("**Status**"); b.bar_chart(ldf["status"].value_counts())
    st.download_button("Download log (CSV)", ldf.to_csv(index=False), "query_log.csv", "text/csv")
else:
    st.caption("No queries yet. Ask something on the Ask & report page and it will appear here.")
