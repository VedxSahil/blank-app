"""PEReport portal: entry point (sidebar document loader + page navigation)."""
import os, tempfile
import streamlit as st
import pe_engine as E
from portal import SAMPLE

st.set_page_config(page_title="PEReport", page_icon="📄", layout="wide")


@st.cache_data(show_spinner="Reading document...")
def parse(name: str, data: bytes):
    suffix = ".pdf" if name.lower().endswith(".pdf") else ".txt"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data); path = f.name
    try:
        return E.load_document(path, name)
    finally:
        os.unlink(path)


with st.sidebar:
    st.markdown("### 📄 PEReport")
    st.caption("Fund Document Assistant")
    files = st.file_uploader("Upload PDF / text documents", type=["pdf", "txt"], accept_multiple_files=True)
    use_sample = st.checkbox("Use fictional sample (Aurelian Peak Fund PPM)", value=not files)

chunks = []
for f in files or []:
    chunks += parse(f.name, f.getvalue())
if use_sample and os.path.exists(SAMPLE):
    chunks += parse(os.path.basename(SAMPLE), open(SAMPLE, "rb").read())
st.session_state["idx"] = E.Index(chunks) if chunks else None
if chunks:
    st.sidebar.success(f"{len(chunks)} passages · {len(st.session_state['idx'].docs)} document(s)")

pg = st.navigation([
    st.Page("app_pages/home.py", title="Portal home", icon="🏠", default=True),
    st.Page("app_pages/ask.py", title="Ask & report", icon="💬"),
    st.Page("app_pages/fees.py", title="Fee calculator", icon="🧮"),
    st.Page("app_pages/dashboard.py", title="Dashboard", icon="📊"),
    st.Page("app_pages/validation.py", title="Validation", icon="✅"),
])
pg.run()
