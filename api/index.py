import os
import sys
from urllib.parse import quote
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from supabase import Client, create_client

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routers import alerts, categories, listing, search  # noqa: E402

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Productswaarde API")
app.include_router(search.router)
app.include_router(listing.router)
app.include_router(categories.router)
app.include_router(alerts.router)


@app.get("/api/health")
def health():
    supabase_status = "not_configured"
    if supabase is not None:
        try:
            supabase.table("listings").select("id").limit(1).execute()
            supabase_status = "connected"
        except Exception:
            supabase_status = "error"

    return {"status": "ok", "supabase": supabase_status}


CATEGORY_SLUGS = ["smartphones", "laptops", "fietsen", "gaming", "cameras", "meubels", "kleding", "autos"]


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    base_url = os.environ.get("BASE_URL", "https://productswaarde.nl")
    return f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n"


@app.get("/sitemap.xml")
def sitemap_xml():
    base_url = os.environ.get("BASE_URL", "https://productswaarde.nl")

    urls = [f"{base_url}/", f"{base_url}/deals.html", f"{base_url}/alerts.html", f"{base_url}/privacy.html"]
    urls += [f"{base_url}/category.html?name={slug}" for slug in CATEGORY_SLUGS]

    if supabase is not None:
        try:
            rows = (
                supabase.table("keyword_stats")
                .select("keyword, active_listings")
                .order("active_listings", desc=True)
                .limit(30)
                .execute()
                .data
            )
            urls += [f"{base_url}/results.html?q={quote(row['keyword'])}" for row in rows]
        except Exception:
            pass

    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    body += [f"  <url><loc>{escape(url)}</loc></url>" for url in urls]
    body.append("</urlset>")

    return Response(content="\n".join(body), media_type="application/xml")


# Local-dev convenience only: Vercel serves frontend/** as static files directly
# (see vercel.json) and never routes those requests through this app in production.
_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
