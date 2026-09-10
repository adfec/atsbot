# ATS Job Alert Pipeline

Daily job alert pipeline running for free on GitHub Actions, with state
persisted as git commits (no external database).

It's an evolution of [Building a Zero-Cost Daily Job Alert Pipeline](https://dzone.com/articles/build-daily-job-alert-pipeline),
with three main improvements over the original:

1. **Direct per-ATS sources instead of scraping a third-party table.**
   The original did regex parsing of markdown/HTML tables from a
   third-party aggregator, which failed silently if the format changed.
   This version queries each ATS's public API directly (Greenhouse,
   Lever, Ashby, SmartRecruiters, Recruitee, Workable, Workday), with
   auto-discovery by slug — no need to manually map which ATS each
   company uses.
2. **Role/keyword filtering with scoring**, instead of pulling
   everything the source returns. Jobs are scored against three role
   families (Engineering Manager, Solutions/Platform Architect, Senior
   Software Engineer) and ranked by relevance.
3. **Role-based fallback search on open sources.** If the company list
   returns no results (or simply to widen the pool), the pipeline also
   searches directly by keyword on public aggregators (Remotive,
   Arbeitnow), without depending on the company being in the curated
   list. These results are flagged separately in the digest — the
   compatibility call is left to the user.

It also keeps what worked well in the original: state in git (dedupe +
rolling window of N days), idempotency, and now a source-health alarm
(if an ATS that normally responds drops to 0, it's reported as a
possible failure, not as "no openings today").

Delivery is 100% native to GitHub: the digest is posted as a comment on
a pinned Issue in the repo itself, using the `GITHUB_TOKEN` Actions
already provides on every run — no SMTP, no app passwords, no personal
account credential involved.

A location/remote filter (`src/location_filter.py`) discards postings
in cities/countries outside the region that also don't accept remote
work — applied equally to company-sourced jobs and to the role-search
fallback, see the "Location filter" section below.

## Structure

```
ats-pipeline/
├── config.yaml                  # target companies + roles/keywords
├── requirements.txt
├── main.py                      # orchestrator
├── src/
│   ├── ats_clients/
│   │   ├── base.py              # NormalizedJob (common schema)
│   │   └── discovery.py         # auto-discovery + per-ATS normalization
│   ├── role_search.py           # fallback: role-based search on open sources
│   ├── filter.py                # role/keyword scoring
│   ├── state.py                 # dedupe + rolling window (git-as-DB)
│   ├── health.py                # zero-result source alarm
│   └── notify.py                # posts the digest as a comment on a GitHub Issue
├── .github/workflows/daily.yml  # daily cron + state commit
├── seen_links.json              # state (updated by the workflow itself)
├── job_history.json             # state
├── source_health.json           # state
└── digest_issue.json            # state: number of the pinned digest issue
```

## Setup

1. Create the repo on GitHub (empty, without a README/gitignore from the
   web UI so it doesn't collide with the ones already in this folder)
   and push these files to it:

   ```bash
   cd ats-pipeline
   git init
   git add .
   git commit -m "Initial commit: ATS job alert pipeline"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```

   (With GitHub CLI instead of creating the repo from the web:
   `gh repo create <your-repo> --private --source=. --push`)

2. Confirm token permissions: in the repo, go to *Settings → Actions
   → General → Workflow permissions* and check it's set to "Read and
   write permissions". The workflow already declares `permissions:
   contents: write` and `issues: write` explicitly, but an
   organization policy can override that at the repo level.
3. Turn on **Watch → All Activity** (or at least "Issues") on the
   repo's main page. That way, every new comment on the pinned
   "📋 Job Alerts — Daily Log" issue reaches you by email or through
   the GitHub app — the pipeline never handles any email itself, and
   therefore **there are no secrets to create**: `GITHUB_TOKEN` is
   injected automatically by Actions on every run.
4. Once you push, the workflow is already registered under the
   *Actions* tab. It runs on its own at 08:00 America/Bogota, and you
   can also trigger it manually from *Actions → Daily Job Alert
   Pipeline → Run workflow*.
5. Check that first run right there: if it fails with a 403 either
   creating the issue or pushing the state, it's the same spot as
   step 2 — check "Workflow permissions" at the repo or org level.

### Running it locally

Outside of Actions, `GITHUB_TOKEN`/`GITHUB_REPOSITORY` don't exist on
their own — you need a Personal Access Token with `repo` scope (or,
more narrowly, `issues:write` on a fine-grained token) and to export
the repo name yourself:

```bash
pip install -r requirements.txt
export GITHUB_TOKEN=ghp_xxx
export GITHUB_REPOSITORY=your-username/your-repo
python main.py
```

## Companies included in `config.yaml`

Curated with a focus on employability from Colombia, in four groups:

- **Established LatAm fintech/SaaS**: Rappi, Addi, Bold, Habi, Truora,
  Finkargo, Akua, Siigo, Clara, Kavak, Nubank, Ualá, dLocal, Clip,
  MercadoLibre, VTEX, Despegar.
- **Edtech**: Platzi, Crehana.
- **Global/US companies with confirmed hiring in Colombia**: Twilio,
  Sezzle, Binance, CaseWare International (Canadian audit fintech,
  with an active dev team in Bogotá/Medellín).
- **Consultancies/IT services with a physical presence in Colombia**:
  Globant, Encora, Endava, Nearsure, ThoughtWorks, Accenture,
  AspenView.

Every entry has a `confidence` field:
- `confirmed`: the ATS and/or active hiring in Colombia was manually
  verified during this project's research.
- `candidate`: the company has strong signals of hiring in
  LatAm/Colombia (recent funding rounds, regional presence,
  Endeavor/unicorn reports), but the ATS and how current its openings
  are gets resolved by `discovery` at runtime — not individually
  verified by hand.

You can add more companies to `config.yaml` with just the slug; the
auto-discovery tries to resolve the ATS on its own. If none respond,
the company simply returns 0 results and doesn't break the pipeline
(see `health.py`).

## Roles/keywords

Defined in `config.yaml` under `roles:` — currently Engineering
Manager, Solutions/Platform Architect, and Senior Software Engineer.
Adding a new role is just adding an entry with its keyword list; the
scoring in `src/filter.py` is generic.

## Location filter

`config.yaml` under `location_filter:` controls which jobs are
considered geographically compatible, applied to both sources
(companies and role search) before role scoring:

- `allow_keywords`: if the reported location contains any of these
  (e.g. "remote", "latam", "colombia"), it's accepted.
- `exclude_keywords`: if it contains any of these (e.g. "us only",
  "onsite", "hybrid"), it's discarded regardless of anything else.
- Empty location → accepted (many legitimate remote postings simply
  don't specify one).
- Any other case (a specific city/country that matched neither list)
  → discarded.

It's a case-insensitive substring filter — adjust the lists directly
in `config.yaml` if you see false positives or negatives, no code
changes needed.

## What's deliberately not included

- ATS without a reliable public API (SAP SuccessFactors, Oracle Taleo,
  Bizneo HR, JazzHR) — these would require per-company HTML scraping,
  more fragile; out of scope for this MVP.
- LinkedIn — it has no public jobs API and explicitly prohibits
  scraping in its terms of service; the only legitimate path is
  LinkedIn Talent Solutions, which requires being an approved partner.
- Any external secret or credential — delivery uses only the
  `GITHUB_TOKEN` Actions injects on its own, no SMTP or third-party
  API keys to manage or rotate.
