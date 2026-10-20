# PEReport web

Next.js (App Router) + TypeScript + Tailwind v4 + Framer Motion. shadcn/ui-style components are
hand-written in `components/ui` because the shadcn registry host was blocked when this was built.

```
npm install
npm run dev                      # needs the API on :8000 (API_URL overrides)
npm run lint && npx tsc --noEmit && npm run build
CHROMIUM_PATH=/path/to/chrome npx playwright test   # starts a FIXTURE API (invented text) and the built app
```
