# Setup: from zero to a live deployment

About 60–90 minutes the first time. Do it in this order.

## 0. Guardrails first (5 min)
- Google Cloud Console → **Billing → Budgets & alerts → $20 budget**, alerts at 50/90/100%.
- Never paste keys into chats, issues, or code. Secrets live in Secret Manager.

## 1. GitHub (2 min)
- github.com/new → `antarctica` → Private → no README → Create.
- Push this repo (or have Claude push it once the repo exists):
  ```
  git remote add origin https://github.com/lyl4cs/antarctica.git
  git push -u origin main
  ```

## 2. Database: Neon (10 min)
- neon.tech → New project `antarctica` (free tier). Copy the **connection string**.
- Apply the schema from your laptop:
  ```
  pip install -e ".[dev,ai]"
  DATABASE_URL='postgresql://...' python infra/migrate.py
  ```
  (pgvector is built into Neon; the migration enables it.)

## 3. Google Cloud (20 min)
- Install the gcloud CLI → `gcloud auth login` → `gcloud auth application-default login`
- Create a project (e.g. `antarctica-ls`), link billing, set the budget alert (step 0).
- Run: `PROJECT_ID=antarctica-ls ./infra/setup_gcp.sh` (it asks for your Neon URL once and stores it in Secret Manager).

## 4. RAG corpus (10 min)
```
python -m scripts.fetch_docs                 # downloads ~40 web.dev / Chrome docs
python -m scripts.ingest_docs --dry-run      # sanity check chunk counts
PROJECT_ID=antarctica-ls DATABASE_URL='...' python -m scripts.ingest_docs
```

## 5. Deploy (15 min)
```
PROJECT_ID=antarctica-ls ./infra/deploy.sh
```
It prints your API URL. Test it:
```
curl -X POST $API/scans -H 'content-type: application/json' -d '{"url":"https://example.com"}'
curl $API/scans/<id>                 # queued -> running -> done (~30-60s)
curl $API/scans/<id>/report
curl "$API/scans/<id>/fixes?limit=3"
```

## 5b. Frontend on Vercel (10 min)
- Apply new migrations first: `DATABASE_URL='...' python infra/migrate.py` (safe to re-run; it only applies files it hasn't seen).
- vercel.com → Add New → Project → `lyl4cs/antarctica`, **Root Directory `frontend`**, env var `VITE_API_URL` = the API URL from step 5. Deploy.
- Allow that origin to call the API (CORS), then check it:
  ```
  PROJECT_ID=antarctica-ls FRONTEND_ORIGIN=https://<your-app>.vercel.app ./infra/deploy.sh
  curl -si $API/health -H 'Origin: https://<your-app>.vercel.app' | grep -i access-control-allow-origin
  ```
  Pass `FRONTEND_ORIGIN` on every future deploy too. Details: `frontend/README.md`.
- Health checks use `/health`, not `/healthz`: Cloud Run's front end reserves `/healthz` and answers it itself with a 404.

## 6. Connect Codex (cloud agent) (10 min)
- chatgpt.com/codex → connect GitHub → select `lyl4cs/antarctica`.
- Create an environment: setup script `pip install -e ".[dev,ai]"`. **Add no secrets.** Agents don't need GCP or the database; tests run fully offline.
- Paste tasks from `docs/TASKS.md` one at a time. Review each PR (on your phone is fine), then merge.
- Equivalent alternative: Claude Code on the web (claude.ai/code) with the same repo. `CLAUDE.md` already points it at these rules.

## 7. Get the resume numbers (the actual point)
- **N sites:** scan 20–40 real sites (yours, Novus, Orland Park pages, public sites).
- **RAG X%→Y%:** build `core/evals/cases.jsonl` from 30+ real findings with reference fixes, then run `python -m core.evals.run_eval core/evals/cases.jsonl`. Spot-check judge verdicts by hand.
- **Lighthouse X→Y:** apply suggested fixes to the Novus store. Scan before and after, 3 runs each, and report the median.
