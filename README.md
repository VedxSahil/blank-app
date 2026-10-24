# Pre-Market Dashboard

A one-page dashboard for the Indian stock market, refreshed every weekday morning.

It shows GIFT Nifty, Nifty 50 and Sensex previous closes, India VIX, USD/INR, Brent crude,
US markets overnight, FII and DII flows, an expected-open gap, eight headlines and a short
morning brief. Numbers come from Claude with web search, so they can be wrong. Missing
numbers show as "not found".

For learning only. Not investment advice.

## How it works

- `.github/workflows/daily-update.yml` runs at 6:30 AM IST, Monday to Friday.
- It runs `scripts/update_dashboard.py`, which sends `scripts/prompt_template.md` and the
  current `index.html` to Claude, then checks the reply before saving it.
- If the check fails, the old `index.html` stays and the run fails.
- If `index.html` changed, the workflow commits and pushes it. GitHub Pages serves it.

## Set up once

1. Add a repository secret named `ANTHROPIC_API_KEY` (Settings > Secrets and variables > Actions).
2. Turn on GitHub Pages (Settings > Pages): deploy from branch, folder `/ (root)`.

## Run it by hand

On GitHub: Actions tab > "Daily dashboard update" > Run workflow.

On your machine:

```
pip install anthropic
export ANTHROPIC_API_KEY=your-key
python scripts/update_dashboard.py
```
