# CUSAT-Pulse

Campus issue tracker where Gemma 4 triages photos, groups duplicate reports with a tool-calling agent, ranks issues, audits repair photos, and every step lands in a hash-chained ledger.

## Run it

The easiest way is `start-demo.bat`, which starts the backend, the frontend and (if installed) the phone tunnel. `stop-demo.bat` stops them.

By hand:

```powershell
# backend
cd backend
python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # then put your key in GEMINI_API_KEY
.\.venv\Scripts\python -m scripts.seed_cusat --fresh
.\.venv\Scripts\python -m uvicorn main:app --port 8000 --reload --timeout-graceful-shutdown 3

# frontend (second terminal)
cd frontend
npm install
npm run dev

# phones (third terminal)
cloudflared tunnel --url http://localhost:5173
```

Demo logins (`DEMO_MODE=true`, code `000000`): students `demo1@cusat.ac.in` to `demo10@cusat.ac.in`; admin `estate@cusat.ac.in`; staff `itsupport@cusat.ac.in`.
Other CUSAT emails get a real OTP by email once `SMTP_*` is set in `backend/.env` (Gmail needs an App Password); until then the code is printed in the backend console.

## Demo helpers

Run these from `backend/`, with the backend stopped for `--fresh`.

- `python -m scripts.seed_cusat --fresh`: wipe and reseed (6 issues, a linked hostel pair, and one flagged screen photo). Add `--ai` to have Gemma describe real photos.
  - Put real photos in `backend/seed_images/` as `sahara_1.jpg` to `sahara_3.jpg`, `athulya_1.jpg` to `athulya_6.jpg`, `aishwarya_1.jpg` to `aishwarya_3.jpg`, `soe_1.jpg`, `cittic_1.jpg`, and `amenity_1.jpg` to `amenity_2.jpg`.
- `python -m scripts.tamper_demo`: quietly edit an old ledger block, then click **Verify chain**. Use `--status` to change an issue's status instead. `--restore` undoes either.
- Campus buildings live in `frontend/src/buildings.js` (from OpenStreetMap). Tapping within 40 m of one picks it automatically.
- Fake fix: on the Resolve tab, point the camera at the before photo on another screen. If the photos match by perceptual hash, closure is blocked without calling Gemma. Otherwise Gemma blocks it.
- `VERIFY_WINDOW_MINUTES` sets the student verification window after a repair: `1440` (24 hours) normally, `2` for a stage demo. Restart the backend after changing `.env`.
- Every successful Gemma answer is cached in `demo_cache.json`. If an API call fails in `DEMO_MODE`, the cached answer is used for the same photo.

## Backend layout

```
backend/
  main.py        creates the app, registers routers, starts the scheduler
  core/          config.py (.env settings) · database.py (tables, triggers) · security.py (OTP, JWT, roles) · errors.py
  schemas/       request + response models per feature (auth, reports, issues, admin, ledger)
  routers/       HTTP endpoints, thin: auth · reports · stream (SSE) · issues · admin · ledger · system
  services/      business logic:
                   reporting (report pipeline)  grouping (Gemma tool-calling agent)
                   verification (repair audits, fake checks, student verification)
                   issues (queries, status changes)  ranking (priority, escalation)
                   ledger (hash chain)  antifake  storage  scheduler
  ai/            client.py (keys, retry, cache) · prompts.py · schemas.py (Gemma JSON schemas) · tasks.py
  scripts/       seed_cusat.py · tamper_demo.py
  tests/         pytest suite + API contract snapshot (tests/golden.json)
```

## Tests

```powershell
cd backend
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q
```

`tests/snapshot.py` drives every endpoint (96 calls) on a throwaway database with Gemma stubbed, and compares status codes and JSON against `tests/golden.json`. Run `python -m tests.snapshot record` only when you change an API response on purpose.

## Gemma calls

- **`ai/tasks.py`:** triage, fix audit, student verification check, fake-claim check, and rank reason plus bilingual work order.
  - Each call uses `response_schema`. If the model rejects JSON mode, it falls back to a prompt-only JSON request.
- **`services/grouping.py`:** the grouping agent.
  - Gemma picks tools: `find_nearby_issues`, `get_issue_photos`, `merge_into_issue`, `create_issue`, `link_related`, `notify_department`.
  - The code enforces the same-building rule and reopens recently fixed issues instead of duplicating them.
  - The agent stops after 8 steps. If the tool loop fails, it falls back to a single compare call.
