import statistics
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Query

from scraper.analyzer import analyze_listing
from scraper.marktplaats import dominant_category, scrape_marktplaats, store_listings, supabase

router = APIRouter()

LIVE_SCRAPE_TIMEOUT = 8.0
ERROR_MESSAGE = "Zoekopdracht tijdelijk niet beschikbaar. Probeer het over enkele minuten opnieuw."


@router.get("/api/search")
def search(q: str = Query(..., min_length=1)):
    keyword = q.strip().lower()

    stats_row = (
        supabase.table("keyword_stats").select("*").eq("keyword", keyword).limit(1).execute().data
    )

    # PATH A: keyword already tracked in Supabase -> instant response from stored data.
    if stats_row:
        listings = (
            supabase.table("listings")
            .select("*")
            .eq("keyword", keyword)
            .eq("status", "active")
            .execute()
            .data
        )
        # Same dominant-category filter used for keyword_stats/deals: off-topic
        # accessories shouldn't appear in the results grid at all, not just lose their badge.
        dominant = dominant_category(listings)
        on_topic_listings = [listing for listing in listings if listing["category"] == dominant] if dominant else listings

        median = stats_row[0]["median_price"]
        return {
            "source": "database",
            "keyword": keyword,
            "stats": stats_row[0],
            "listings": [analyze_listing(listing, median) for listing in on_topic_listings],
        }

    # PATH B: unknown keyword -> live scrape, timeboxed to 8 seconds.
    try:
        raw_listings = scrape_marktplaats(keyword, timeout=LIVE_SCRAPE_TIMEOUT)
    except (httpx.HTTPError, httpx.TimeoutException):
        return {"source": "error", "message": ERROR_MESSAGE}

    if not raw_listings:
        return {"source": "error", "message": ERROR_MESSAGE}

    store_listings(keyword, raw_listings)
    supabase.table("scraper_queue").upsert(
        {"keyword": keyword, "added_at": datetime.now(timezone.utc).isoformat(), "active": True},
        on_conflict="keyword",
    ).execute()

    dominant = dominant_category(raw_listings)
    on_topic_listings = [listing for listing in raw_listings if listing["category"] == dominant] if dominant else raw_listings

    live_prices = [listing["price"] for listing in on_topic_listings if listing["price"]]
    live_median = statistics.median(live_prices) if live_prices else None

    return {
        "source": "live",
        "keyword": keyword,
        "listings": [analyze_listing(listing, live_median) for listing in on_topic_listings],
    }


@router.get("/api/deals")
def deals(limit: int = 20):
    active_listings = supabase.table("listings").select("*").eq("status", "active").execute().data
    median_by_keyword = {
        row["keyword"]: row["median_price"]
        for row in supabase.table("keyword_stats").select("keyword, median_price").execute().data
    }

    # Sponsored/loosely-matched ads from unrelated (sub)categories sometimes get tagged with a
    # keyword they don't belong to (e.g. a phone case or Joy-Con controller under "iphone 13" /
    # "nintendo switch"); comparing their price against that keyword's median produces nonsense
    # deal scores, so only the dominant leaf category per keyword is eligible for "best deals".
    listings_by_keyword: dict[str, list[dict]] = {}
    for listing in active_listings:
        listings_by_keyword.setdefault(listing["keyword"], []).append(listing)
    dominant_category_by_keyword = {
        keyword: dominant_category(rows) for keyword, rows in listings_by_keyword.items()
    }

    best_deals = []
    for listing in active_listings:
        analyzed = analyze_listing(listing, median_by_keyword.get(listing["keyword"]))
        on_topic = listing["category"] == dominant_category_by_keyword.get(listing["keyword"])
        if on_topic and analyzed["deal_score"] == "\U0001f7e2 Goede deal":
            best_deals.append(analyzed)

    best_deals.sort(key=lambda listing: listing["discount_percent"] or 0, reverse=True)

    return {
        "source": "database",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "deals": best_deals[:limit],
    }


@router.get("/api/stats/{keyword}")
def keyword_stats(keyword: str):
    keyword = keyword.strip().lower()

    stats_row = (
        supabase.table("keyword_stats").select("*").eq("keyword", keyword).limit(1).execute().data
    )
    if not stats_row:
        return {"keyword": keyword, "found": False}

    listing_ids = [
        row["id"]
        for row in supabase.table("listings").select("id").eq("keyword", keyword).execute().data
    ]

    price_history: list[dict] = []
    if listing_ids:
        ninety_days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        snapshots = (
            supabase.table("price_snapshots")
            .select("price, scraped_at")
            .in_("listing_id", listing_ids)
            .gte("scraped_at", ninety_days_ago)
            .execute()
            .data
        )
        prices_by_day: dict[str, list[float]] = {}
        for snapshot in snapshots:
            day = snapshot["scraped_at"][:10]
            prices_by_day.setdefault(day, []).append(snapshot["price"])
        price_history = [
            {"date": day, "median_price": statistics.median(prices), "count": len(prices)}
            for day, prices in sorted(prices_by_day.items())
        ]

    return {
        "keyword": keyword,
        "found": True,
        "stats": stats_row[0],
        "price_history": price_history,
    }
