PY=.venv/bin
check:
	$(PY)/ruff check . && $(PY)/ruff format --check . && $(PY)/mypy && $(PY)/pytest -q
