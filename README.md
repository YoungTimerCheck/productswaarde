# Productswaarde.nl

A Dutch secondhand price checker for Marktplaats listings. Search a product or paste a
listing link, and get a deal-score (🟢 goede deal / 🟡 gemiddeld / 🔴 te duur) based on
the current market median, plus optional price alerts by email.

**Stack:** FastAPI (Python) + Supabase (Postgres) + plain HTML/Tailwind CDN frontend,
deployed on Vercel. Scraping runs on a GitHub Actions cron.

## Folder structure

```
productswaarde/
├── api/index.py          FastAPI app — entry point for both local dev and Vercel
├── routers/               API endpoints, one file per concern
│   ├── search.py           GET /api/search, /api/deals, /api/stats/{keyword}
│   ├── listing.py          GET /api/listing (single Marktplaats URL analysis)
│   ├── categories.py       GET /api/categories
│   └── alerts.py           POST /api/alerts, GET /api/alerts/unsubscribe/{token}, email sending
├── scraper/
│   ├── marktplaats.py       Scrapes Marktplaats' search API, stores in Supabase, checks alerts
│   ├── analyzer.py          Deal-score calculation, category/price-type translation
│   └── run.py                Entry point — scrapes a list of keywords (CLI or GitHub Actions)
├── frontend/               Static HTML pages + shared static/app.js and static/style.css
├── .github/workflows/scraper.yml   Runs the scraper every 4 hours + manual trigger
├── supabase_schema.sql     Run this once in the Supabase SQL editor
└── vercel.json             Deployment/routing config
```

## Local development setup

1. **Create a virtualenv and install dependencies:**
   ```bash
   py -m venv venv
   ./venv/Scripts/python.exe -m pip install -r requirements.txt
   ```

2. **Create Supabase tables** — open the SQL editor in your Supabase project and run the
   contents of `supabase_schema.sql`.

3. **Configure environment variables** — copy `.env.example` to `.env` and fill in:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-key
   SMTP_HOST=smtp.hostinger.com
   SMTP_PORT=465
   SMTP_USER=alerts@productswaarde.nl
   SMTP_PASSWORD=your-mailbox-password
   BASE_URL=https://productswaarde.nl
   ```
   `.env` is gitignored — never commit it.

4. **Run the API + frontend together:**
   ```bash
   ./venv/Scripts/python.exe -m uvicorn api.index:app --reload --port 8000
   ```
   Open http://127.0.0.1:8000/ — the FastAPI app also serves `frontend/` as static files
   locally (see the `StaticFiles` mount at the bottom of `api/index.py`), so the whole
   site works from one origin without CORS. This mount is dev-only; in production
   `vercel.json` serves `frontend/**` directly.

5. **Run the scraper manually:**
   ```bash
   ./venv/Scripts/python.exe scraper/run.py                 # all default + queued keywords
   ./venv/Scripts/python.exe scraper/run.py "iphone 13"      # just one keyword
   ```

## Adding new keywords to the scraper

Two ways a keyword gets tracked:
- **Automatically**: any keyword a visitor searches that isn't in the database yet gets
  live-scraped once, then upserted into the `scraper_queue` table — it's picked up by
  every future scheduled run.
- **Manually**: add it to `DEFAULT_KEYWORDS` in `scraper/run.py`, or insert a row
  directly into `scraper_queue` (`keyword`, `active: true`).

`scraper/run.py`'s `resolve_keywords()` scrapes the union of both sets on every run.

## GitHub Actions setup (automated scraping)

The workflow at `.github/workflows/scraper.yml` runs every 4 hours (`cron: '0 */4 * * *'`)
and supports manual runs via `workflow_dispatch` (optionally scoped to one keyword, for
testing). It needs these repo secrets — **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `SUPABASE_URL` | your Supabase project URL |
| `SUPABASE_KEY` | your Supabase anon key |
| `SMTP_HOST` | `smtp.hostinger.com` (or your provider) |
| `SMTP_PORT` | `465` |
| `SMTP_USER` | the sending mailbox address |
| `SMTP_PASSWORD` | the mailbox password |
| `BASE_URL` | `https://productswaarde.nl` |

Via `gh` CLI instead of the web UI:
```bash
gh secret set SUPABASE_URL --repo <owner>/<repo>
# (paste the value when prompted, or pipe it in: echo -n "value" | gh secret set NAME --repo <owner>/<repo>)
```

## Vercel deployment

```bash
npm install -g vercel
vercel login
vercel                 # first run: links/creates the project, deploys a preview
vercel --prod          # deploys to production
```

Add the same 7 environment variables from the table above in the Vercel dashboard
(**Project → Settings → Environment Variables**) — Vercel doesn't read `.env` or GitHub
secrets automatically. Then connect the domain under **Project → Settings → Domains**.

`vercel.json` builds `api/index.py` as a Python serverless function and serves
`frontend/**` as static files, with `/api/*`, `/sitemap.xml`, and `/robots.txt` routed to
the Python function and everything else served directly from `frontend/`.
