# CUSAT-Pulse

Campus issue tracker where Gemma 4 triages photos, groups duplicate reports with a tool-calling agent, ranks issues, audits repair photos, and every step lands in a hash-chained ledger.

## Run it

```powershell
# backend
cd backend
python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # then put your key in GEMINI_API_KEY
.\.venv\Scripts\python seed_cusat.py --fresh
.\.venv\Scripts\python -m uvicorn main:app --port 8000 --reload --timeout-graceful-shutdown 3

# frontend (second terminal)
cd frontend
npm install
npm run dev

# phones (third terminal)
cloudflared tunnel --url http://localhost:5173
```

Demo logins (`DEMO_MODE=true`, code `000000`): students `demo1@cusat.ac.in` to `demo10@cusat.ac.in`; admin `estate@cusat.ac.in`; staff `itsupport@cusat.ac.in`.
Other CUSAT emails get a real OTP printed in the backend console.

## Demo helpers

- `python seed_cusat.py --fresh`: wipe and reseed (6 issues, a linked hostel pair, and one flagged screen photo). Put real photos in `backend/seed_images/` as `sahara_1.jpg` to `sahara_3.jpg`, `athulya_1.jpg` to `athulya_6.jpg`, `aishwarya_1.jpg` to `aishwarya_3.jpg`, `soe_1.jpg`, `cittic_1.jpg`, and `amenity_1.jpg` to `amenity_2.jpg`.
- Campus buildings live in `frontend/src/buildings.js` (from OpenStreetMap). Tapping within 40 m of one picks it automatically.
- `python tamper_demo.py`: quietly edit an old ledger block, then click **Verify chain**. Use `--status` to change an issue's status instead. `--restore` undoes either.
- Fake fix: on the Resolve tab, point the camera at the before photo on another screen. If the photos match by perceptual hash, closure is blocked without calling Gemma. Otherwise Gemma blocks it.
- `VERIFY_WINDOW_MINUTES=2` gives a 2-minute student check.
- Every successful Gemma answer is cached in `demo_cache.json`. If an API call fails in `DEMO_MODE`, the cached answer is used, so rehearse the live photos once.

## Gemma calls

`backend/gemma.py`: triage, fix audit, dispute check, and rank reason plus bilingual work order. Each call uses `response_schema`. If the model rejects JSON mode, it falls back to a prompt-only JSON request.
`backend/agent.py`: the grouping agent. Gemma picks tools (`find_nearby_issues`, `get_issue_photos`, `merge_into_issue`, `create_issue`, `link_related`, `notify_department`). The code enforces the same-building rule. The agent stops after 6 steps, and if the tool loop fails it falls back to a single compare call.
