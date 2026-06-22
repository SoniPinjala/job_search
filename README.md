# JobSearch — automated, free, fresh-job finder

Scheduled job search that pulls **fresh** postings from job APIs and company
career boards, flags **H1B sponsors**, writes a **custom referral message** for
each, and appends everything to a **Google Sheet** with an *Applied / Not applied*
dropdown. Runs every ~30 minutes on **GitHub Actions** — all on free tiers.

Built for an international student targeting Data Science / ML / AI / SWE roles in
the USA, but every part is configurable.

---

## What it does (and the honest limits)

| Goal | How it's actually done |
|---|---|
| Search LinkedIn / Indeed | **Indirectly**, via Google-for-Jobs (JSearch), which indexes them. Direct scraping is against their ToS and gets blocked — we don't do it. |
| Company career sites | **Greenhouse / Lever / Ashby public board APIs** — the legit, free, no-key way to read jobs straight off company pages. |
| Broad coverage | **Adzuna** + **Jooble** free APIs. |
| "< 50 applicants" | Not available for free anywhere. We use a **freshness proxy**: only postings first seen within `max_age_hours` (default 6h) — newly posted ≈ few applicants. |
| Custom referral message | **Google Gemini** (free tier) personalised from your `profile`. Falls back to a smart template if no key. |
| H1B priority | Company names are matched against known H1B sponsors (seed list shipped; swap in the full **USCIS/DOL** dataset). Flagged, and sorted to the top. Fuzzy match — strong signal, not a guarantee. |
| Output | Private **Google Sheet**: Date · Company · Role · Location · Link · Source · H1B? · Match · Referral message · Applied? (dropdown). De-duplicated across runs. |

**Degrades gracefully:** with zero API keys it still runs on the ATS boards alone.

---

## Architecture

```
docs/index.html (GitHub Pages)      GitHub Actions (cron)             Google Sheet
  edit config.yaml  ───commit──►  search.yml   every 30m  ─┐
                                  deep-crawl.yml every 6h  ─┴─► fetch
                                       │  Adzuna · Jooble · Greenhouse/Lever/Ashby
                                       │  (+ JSearch in deep runs only)
                                       ▼
                          filter (role + US + freshness) → dedupe
                                       ▼  + H1B lookup  + referral message
                                       ▼
                                  append new rows ───────────────►  you review,
                                                                    flip Applied?
```

Cadence is tiered so every source stays inside its free quota — JSearch (~200
calls/**month**) only runs in the 6-hour deep crawl; Adzuna/Jooble (1 cheap call
each) and the no-key ATS boards run every 30 minutes.

---

## One-time setup (~20 min, all free)

### 0. Get the code into your own **public** GitHub repo
Public repo = unlimited free Actions minutes. Secrets stay encrypted; the Sheet
stays private; your profile lives in a Secret — nothing personal is exposed.

```bash
git init && git add . && git commit -m "init job search"
gh repo create job-search --public --source=. --push   # or create it in the UI
```

### 1. Google Sheet + service account (free)
1. Create a blank Google Sheet. Copy its ID from the URL
   (`docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`).
2. Go to <https://console.cloud.google.com/> → new project → **APIs & Services →
   Enable APIs** → enable **Google Sheets API**.
3. **Credentials → Create credentials → Service account** → create. Then open the
   service account → **Keys → Add key → JSON** → download it.
4. **Share your Sheet** (Editor) with the service account's email
   (`...@...iam.gserviceaccount.com`, it's in the JSON).

### 2. Free API keys
| Service | Where | Secret name |
|---|---|---|
| Adzuna | <https://developer.adzuna.com/> | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` |
| Jooble | <https://jooble.org/api/about> | `JOOBLE_KEY` |
| JSearch (optional) | RapidAPI → JSearch | `JSEARCH_KEY` |
| Gemini (optional) | <https://aistudio.google.com/app/apikey> | `GEMINI_API_KEY` |

Adzuna/Jooble/JSearch/Gemini are all optional — skip any and that source is
simply disabled.

### 3. Add GitHub Secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**:

- `GOOGLE_SHEET_ID` — the ID from step 1.
- `GOOGLE_SERVICE_ACCOUNT_JSON` — paste the **entire** JSON file contents.
- `PROFILE_BLURB` — your profile paragraph (see `profile.example.md`).
- `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JOOBLE_KEY`, and optionally
  `JSEARCH_KEY`, `GEMINI_API_KEY`.

### 4. Initialise the Sheet & turn it on
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# local creds for setup: export the same values, or drop the JSON as service_account.json
export GOOGLE_SHEET_ID=...   # and GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json
python scripts/setup_sheet.py        # creates headers + the Applied? dropdown
```
Then in GitHub: **Actions** tab → enable workflows → open **job-search-frequent**
→ **Run workflow** to test immediately. After that it runs on its own.

### 5. (Optional) the config webpage
**Settings → Pages → Source: Deploy from branch → `main` / `/docs`.** Your page
appears at `https://<owner>.github.io/<repo>/`. Edit roles/description/companies
there and click **Save to GitHub** (needs a fine-grained token with *Contents:
read & write*), or just **Download** and commit `config.yaml` yourself.

---

## Running & testing locally

```bash
python main.py --dry-run            # prints matches, writes nothing, needs no Google creds
python main.py --mode frequent      # the real 30-min run
python main.py --mode deep          # adds JSearch
python scripts/verify_companies.py  # check which company slugs resolve
```

## Configuration — `config.yaml`
Roles, description, location, filters, H1B behaviour, and the company board slugs.
It's commented; edit by hand or via the webpage. Key knobs:
- `filters.max_age_hours` — the freshness window (lower = fewer, fresher results).
- `filters.min_match_score` — `0` = rank only; raise to also drop weak matches.
- `h1b.require` — set `true` to keep **only** known sponsors.

## Upgrading the H1B data (optional but recommended)
The shipped `data/h1b_sponsors.csv` is a curated seed. For real filing counts:
1. Download the **USCIS H-1B Employer Data Hub** CSV (or DOL LCA data) — links in
   `scripts/build_h1b_dataset.py`.
2. `python scripts/build_h1b_dataset.py --input ~/Downloads/employer_hub.csv --source uscis-2024`
3. Commit the regenerated `data/h1b_sponsors.csv`.

---

## Free-tier budget (why it stays $0)
| Resource | Free limit | Our usage |
|---|---|---|
| GitHub Actions | unlimited on public repos | ~48 short runs/day |
| Adzuna | ~250 calls/day | 1 call/run |
| Jooble | generous | 1 call/run |
| JSearch | ~200 calls/month | ~4 calls/day (deep only) |
| Gemini | ~1,500 calls/day (flash) | 1 per *new* job |
| Google Sheets API | 60 reads+writes/min/user | a couple per run |

## Project layout
```
config.yaml            search settings (no secrets)
profile.md             your blurb (git-ignored; or use PROFILE_BLURB secret)
main.py                orchestrator
src/                   config, models, matching, h1b, referral, sheets, sources/
scripts/               setup_sheet · verify_companies · build_h1b_dataset
data/h1b_sponsors.csv  sponsor lookup (seed; replace with official data)
docs/index.html        config webpage (GitHub Pages)
.github/workflows/     search.yml (30m) · deep-crawl.yml (6h)
```

## Notes & etiquette
- We only hit official/public APIs and never scrape LinkedIn/Indeed directly.
- The freshness proxy is a substitute for applicant counts, not the same thing.
- H1B flags are a strong signal from historical data, not a promise for any role.
