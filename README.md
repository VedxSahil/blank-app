# PEReport — Fund Document Assistant

RAG over private-fund documents: section-tagged chunking, BM25 retrieval with citations, a refusal rule for unsupported
questions, fee arithmetic computed in code, a quarterly-style report draft and a validation harness.

* `pe_engine.py` — the engine (stdlib + pypdf). CLI: `python pe_engine.py doc.pdf eval/gold_aurelian.json`
* `streamlit_app.py` — the web app: `pip install -r requirements.txt && streamlit run streamlit_app.py`
* `docs/index.html` — the same pipeline as a single static page (no server)
* `docs/sample/` — a fictional sample PPM (Aurelian Peak Fund); `eval/gold_aurelian.json` — its 37-question validation set
* `report/` — project report sources

Deploy publicly: share.streamlit.io → New app → this repo, branch `claude/stoic-edison-nxyb7y`, main file `streamlit_app.py`.
