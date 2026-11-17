# StaySmart Frontend

React + TypeScript + Vite frontend for the StaySmart hotel concierge.

## Scripts

```bash
npm run dev          # start dev server with HMR
npm run build        # type-check and build for production
npm run preview      # preview the production build
npm run lint         # run Oxlint
npm run format       # format with Prettier
npm run format:check # check formatting without writing
npm test             # run Playwright E2E tests (starts backend + dev server)
```

E2E tests live in `e2e/` and run against a scripted-LLM backend harness
(`scripts/e2e_backend.py`), so they are deterministic and need no external LLM.
Artifacts (results JSON, screenshots, failure traces) are written to
`artifacts/e2e_ui/`.

## Tooling

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react) (React over Oxc)
- Oxlint for linting, Prettier for formatting
- Playwright for E2E tests
