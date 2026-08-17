import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI
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


# Local-dev convenience only: Vercel serves frontend/** as static files directly
# (see vercel.json) and never routes those requests through this app in production.
_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
