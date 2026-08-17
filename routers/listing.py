import json
import re
import statistics
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query

from scraper.analyzer import analyze_listing
from scraper.marktplaats import HEADERS, scrape_marktplaats, store_listings, supabase

router = APIRouter()

_CONFIG_KEY = "window.__CONFIG__ = "
_DESCRIPTION_RE = re.compile(
    r'class="Description-module-description"><div data-collapsable="description">(.*?)</div>',
    re.S,
)
_CONDITION_RE = re.compile(
    r'Attributes-module-label">Conditie</div><div class="Attributes-module-value">([^<]+)</div>'
)


def _extract_listing_config(html: str) -> dict:
    idx = html.find(_CONFIG_KEY)
    if idx == -1:
        raise ValueError("listing config not found in page")
    data, _ = json.JSONDecoder().raw_decode(html, idx + len(_CONFIG_KEY))
    return data["listing"]


def _parse_detail_page(url: str, html: str) -> tuple[dict, str | None]:
    raw = _extract_listing_config(html)

    price_info = raw.get("priceInfo", {})
    seller = raw.get("seller", {})
    category = raw.get("category") or {}

    days_listed = 0
    since = raw.get("stats", {}).get("since")
    if since:
        try:
            listed_at = datetime.fromisoformat(since.replace("Z", "+00:00"))
            days_listed = max((datetime.now(timezone.utc) - listed_at).days, 0)
        except ValueError:
            pass

    image_url = None
    image_urls = raw.get("gallery", {}).get("imageUrls") or []
    if image_urls:
        image_url = "https:" + image_urls[0].replace("$_#.jpg", "$_82.jpg")

    listing = {
        "marktplaats_id": raw.get("itemId"),
        "title": raw.get("title"),
        "price": price_info.get("priceCents", 0) / 100 if price_info.get("priceCents") is not None else None,
        "price_type": price_info.get("priceType"),
        "condition": _CONDITION_RE.search(html).group(1) if _CONDITION_RE.search(html) else None,
        "seller_type": "particulier" if seller.get("sellerType") == "CONSUMER" else "bedrijf",
        "location": seller.get("location", {}).get("cityName"),
        "keyword": None,
        "url": url,
        "image_url": image_url,
        "days_listed": days_listed,
        "status": "active",
        # ground-truth category from the listing's own page, more precise than URL-slug guessing
        "category_name_ground_truth": category.get("name"),
        "category_group_ground_truth": category.get("parentName"),
    }

    description_match = _DESCRIPTION_RE.search(html)
    description = description_match.group(1) if description_match else None

    return listing, description


def _find_median(listing: dict) -> float | None:
    marktplaats_id = listing["marktplaats_id"]

    # Best case: we already track this exact listing under a known keyword.
    existing = (
        supabase.table("listings")
        .select("keyword")
        .eq("marktplaats_id", marktplaats_id)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        stats_row = (
            supabase.table("keyword_stats")
            .select("median_price")
            .eq("keyword", existing[0]["keyword"])
            .limit(1)
            .execute()
            .data
        )
        if stats_row:
            return stats_row[0]["median_price"]

    # Fallback: derive a search keyword from the title and scrape live for a fresh median.
    title_words = re.findall(r"[A-Za-z0-9]+", listing["title"] or "")
    keyword_guess = " ".join(title_words[:3]).lower()
    if not keyword_guess:
        return None

    try:
        raw_listings = scrape_marktplaats(keyword_guess, timeout=8.0)
    except (httpx.HTTPError, httpx.TimeoutException):
        return None

    if not raw_listings:
        return None

    store_listings(keyword_guess, raw_listings)
    prices = [item["price"] for item in raw_listings if item["price"]]
    return statistics.median(prices) if prices else None


@router.get("/api/listing")
def get_listing(url: str = Query(...)):
    if "marktplaats.nl/v/" not in url:
        raise HTTPException(status_code=400, detail="Ongeldige Marktplaats link.")

    try:
        response = httpx.get(url, headers=HEADERS, timeout=8.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Kon de advertentie niet ophalen.")

    try:
        listing, description = _parse_detail_page(url, response.text)
    except (ValueError, KeyError):
        raise HTTPException(status_code=502, detail="Kon advertentiegegevens niet lezen.")

    median = _find_median(listing)
    analyzed = analyze_listing(listing, median, description=description)

    # Ground-truth category from the listing page itself overrides the URL-slug guess.
    if listing.get("category_name_ground_truth"):
        analyzed["category_name"] = listing["category_name_ground_truth"]
    if listing.get("category_group_ground_truth"):
        analyzed["category_group"] = listing["category_group_ground_truth"]
    analyzed.pop("category_name_ground_truth", None)
    analyzed.pop("category_group_ground_truth", None)

    return {"source": "live", "listing": analyzed}
