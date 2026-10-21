import streamlit as st
import pe_engine as E
from portal import require_index

idx = require_index()
st.title("🧮 Fee calculator")
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
