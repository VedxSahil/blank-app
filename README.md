# PEReport — Fund Document Assistant

RAG over private-fund documents: section-tagged chunking, BM25 retrieval with citations, a refusal rule for unsupported
questions, fee arithmetic computed in code, a quarterly-style report draft and a validation harness.

* `pe_engine.py` — the engine (stdlib + pypdf). CLI: `python pe_engine.py doc.pdf eval/gold_aurelian.json`
* `streamlit_app.py` + `app_pages/` + `portal.py` — the web portal (home, Ask & report, Fee calculator, Dashboard, Validation): `pip install -r requirements.txt && streamlit run streamlit_app.py`
* `docs/index.html` — the same pipeline as a single static page (no server)
* `docs/sample/` — a fictional sample PPM (Aurelian Peak Fund); `eval/gold_aurelian.json` — its 37-question validation set
* `report/` — project report sources

Deploy publicly: share.streamlit.io → New app → this repo, branch `claude/stoic-edison-nxyb7y`, main file `streamlit_app.py`.

## Data sources
* `docs/sample/Aurelian_Peak_Fund_Sample_PPM.pdf` — fictional sample PPM.
* `data/ILPA-Reporting-Template-v2.0.xlsx` — the ILPA Reporting Template v2.0 (example workbook, © ILPA, published for public use at ilpa.org). Loaded as rows with section, label and period (QTD/YTD/ITD) so questions about contributions, distributions, NAV, commitments and fees are answered with row-level citations; DPI, RVPI and TVPI are computed in code from the LP capital account.
* `eval/gold_aurelian.json` (37 questions) and `eval/gold_ilpa.json` (28 questions) — validation sets.
