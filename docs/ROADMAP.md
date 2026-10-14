# Roadmap: Oct 14 → Google FDE application (deadline Nov 20)

Your weekly schedule: classes Mon and Wed, work Tue/Thu/Fri 9–4.
Agents run on work days, when you only review PRs on your phone. Owner tasks happen on class-day evenings and weekends.

| Week | Agents | You | Done when |
|---|---|---|---|
| **Oct 14–18** | T1 local dev, T2 API + DB | O1 GCP setup and budget alert. Read the T1/T2 PRs. Run `run_lighthouse.py` locally on 3 sites. | A scan is stored in local Postgres |
| **Oct 19–25** | T3 worker, T5 docs fetch | O3 RAG: chunk and embed the docs, write the retrieval query, answer the 5 questions | `retrieve("render blocking css")` returns sensible chunks |
| **Oct 26–Nov 1** | T4 deploy scripts, T6 GitHub Action | O8 first deploy to Cloud Run. O4 agent pipeline v1 (no reflection yet). | Live URL scans a site end to end on GCP |
| **Nov 2–8** | Fixes and tests from your review notes | O4 self-reflection. O5 eval set (30+ cases). O7 discovery talks. | Eval script prints accuracy with and without RAG |
| **Nov 9–15** | Polish, README, architecture diagram | O6 measure everything. Fill the resume placeholders. Make the repo public. | Every red number on the resume is real |
| **Apply** | | Apply as soon as a Google application slot frees up (and before Nov 20), with the referral | Submitted |

Rule: if a week slips, cut scope (fewer agents, fewer docs), **don't skip evals**. The eval numbers are what get you the interview.

Leetcode keeps going in parallel: 3 new + 1 redo a day, as planned.
