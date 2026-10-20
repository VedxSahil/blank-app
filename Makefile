PY=.venv/bin
check:
	$(PY)/ruff check . && $(PY)/ruff format --check . && $(PY)/mypy && $(PY)/pytest -q

web-check:
	cd web && npx tsc --noEmit && npx eslint && npm run build
e2e:
	cd web && CHROMIUM_PATH=$${CHROMIUM_PATH:-/opt/pw-browsers/chromium-1194/chrome-linux/chrome} npx playwright test
