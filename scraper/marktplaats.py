import os
import statistics
from collections import Counter
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

supabase: Client = create_client(
    os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"]
)

SEARCH_URL = "https://www.marktplaats.nl/lrp/api/search"
BASE_URL = "https://www.marktplaats.nl"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_DUTCH_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


def _parse_days_listed(date_label: str | None) -> int:
    if not date_label:
        return 0
    label = date_label.strip().lower()
    if label == "vandaag":
        return 0
    if label == "gisteren":
        return 1

    parts = label.split()
    if len(parts) == 3:
        day_str, month_str, year_str = parts
        month = _DUTCH_MONTHS.get(month_str)
        if month:
            try:
                listed = datetime(2000 + int(year_str), month, int(day_str))
                return max((datetime.now() - listed).days, 0)
            except ValueError:
                pass
    return 0


def _parse_listing(raw: dict, keyword: str) -> dict | None:
    item_id = raw.get("itemId")
    if not item_id:
        return None

    price_info = raw.get("priceInfo", {})
    price_cents = price_info.get("priceCents")

    condition = next(
        (a["value"] for a in raw.get("attributes", []) if a.get("key") == "condition"),
        None,
    )

    seller_info = raw.get("sellerInformation", {})
    # Marktplaats' search API has no explicit "particulier vs bedrijf" field.
    # Sponsored/dealer listings (Admarkt) are the only ones carrying a seller website link.
    seller_type = "bedrijf" if seller_info.get("showWebsiteUrl") else "particulier"

    vip_url = raw.get("vipUrl")
    url = (BASE_URL + vip_url) if vip_url else seller_info.get("sellerWebsiteUrl")

    image_url = None
    pictures = raw.get("pictures") or []
    if pictures:
        image_url = pictures[0].get("mediumUrl") or pictures[0].get("url")
    elif raw.get("imageUrls"):
        image_url = "https:" + raw["imageUrls"][0]

    return {
        "marktplaats_id": item_id,
        "title": raw.get("title"),
        "price": price_cents / 100 if price_cents is not None else None,
        "price_type": price_info.get("priceType"),
        "condition": condition,
        "seller_type": seller_type,
        "location": raw.get("location", {}).get("cityName"),
        # The search API doesn't return category names, only a numeric categoryId.
        "category": str(raw["categoryId"]) if raw.get("categoryId") is not None else None,
        "keyword": keyword,
        "url": url,
        "image_url": image_url,
        "days_listed": _parse_days_listed(raw.get("date")),
    }


def scrape_marktplaats(keyword: str, limit: int = 30, timeout: float = 8.0) -> list[dict]:
    params = {
        "query": keyword,
        "limit": limit,
        "offset": 0,
        "searchInTitleAndDescription": "true",
    }
    response = httpx.get(SEARCH_URL, params=params, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    listings = [_parse_listing(raw, keyword) for raw in data.get("listings", [])]
    return [listing for listing in listings if listing is not None]


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * pct
    f, c = int(k), min(int(k) + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _recalculate_keyword_stats(keyword: str) -> None:
    rows = (
        supabase.table("listings")
        .select("price, status, category")
        .eq("keyword", keyword)
        .execute()
        .data
    )

    # Marktplaats injects sponsored ads / loosely-matched items from unrelated (sub)categories
    # into every search (e.g. a phone case or Joy-Con controller showing up under "iphone 13" /
    # "nintendo switch"). Only the dominant leaf category's listings represent the actual
    # product being searched for, so median/avg are computed from those alone.
    active_rows = [r for r in rows if r["status"] == "active"]
    dominant_category = (
        Counter(r["category"] for r in active_rows).most_common(1)[0][0] if active_rows else None
    )

    # Exclude price <= 0: open "FAST_BID" auctions report priceCents=0 (no minimum bid set),
    # which isn't a real price signal and would drag the median down artificially.
    active_prices = sorted(
        r["price"] for r in active_rows if r["price"] and r["category"] == dominant_category
    )

    supabase.table("keyword_stats").upsert(
        {
            "keyword": keyword,
            "avg_price": statistics.fmean(active_prices) if active_prices else None,
            "median_price": _median(active_prices),
            "p25_price": _percentile(active_prices, 0.25),
            "p75_price": _percentile(active_prices, 0.75),
            "total_listings": len(rows),
            "active_listings": len(active_prices),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="keyword",
    ).execute()


def check_alerts(keyword: str) -> None:
    # Deferred import: routers.alerts imports `supabase` from this module at load time,
    # so importing it back at module level here would create a circular import.
    from routers.alerts import send_match_email

    alerts = (
        supabase.table("alerts")
        .select("*")
        .eq("keyword", keyword)
        .eq("active", True)
        .execute()
        .data
    )
    if not alerts:
        return

    stats_row = (
        supabase.table("keyword_stats").select("median_price").eq("keyword", keyword).limit(1).execute().data
    )
    median_price = stats_row[0]["median_price"] if stats_row else None

    for alert in alerts:
        query = (
            supabase.table("listings")
            .select("*")
            .eq("keyword", keyword)
            .eq("status", "active")
            .gt("price", 0)
            .lte("price", alert["max_price"])
        )
        if alert.get("last_notified"):
            query = query.gt("first_seen", alert["last_notified"])
        matches = query.order("price").limit(1).execute().data
        if not matches:
            continue

        try:
            send_match_email(alert, matches[0], median_price)
        except Exception as exc:
            print(f"  failed to send match email for alert {alert['id']}: {exc}")
            continue

        supabase.table("alerts").update(
            {
                "last_notified": datetime.now(timezone.utc).isoformat(),
                "alert_count": (alert.get("alert_count") or 0) + 1,
            }
        ).eq("id", alert["id"]).execute()


def store_listings(keyword: str, parsed_listings: list[dict]) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    scraped_ids = {listing["marktplaats_id"] for listing in parsed_listings}

    existing_rows = (
        supabase.table("listings")
        .select("marktplaats_id, first_seen")
        .eq("keyword", keyword)
        .execute()
        .data
    )
    existing_first_seen = {row["marktplaats_id"]: row["first_seen"] for row in existing_rows}
    existing_ids = set(existing_first_seen)

    payload = [
        {
            **listing,
            "first_seen": existing_first_seen.get(listing["marktplaats_id"], now),
            "last_seen": now,
            "status": "active",
        }
        for listing in parsed_listings
    ]
    if payload:
        upserted_rows = supabase.table("listings").upsert(payload, on_conflict="marktplaats_id").execute().data
        snapshot_payload = [
            {"listing_id": row["id"], "price": row["price"], "scraped_at": now}
            for row in upserted_rows
            if row.get("price")
        ]
        if snapshot_payload:
            supabase.table("price_snapshots").insert(snapshot_payload).execute()

    disappeared_ids = existing_ids - scraped_ids
    if disappeared_ids:
        supabase.table("listings").update({"status": "sold"}).in_(
            "marktplaats_id", list(disappeared_ids)
        ).execute()

    _recalculate_keyword_stats(keyword)
    check_alerts(keyword)

    return {
        "fetched": len(parsed_listings),
        "new": len(scraped_ids - existing_ids),
        "updated": len(scraped_ids & existing_ids),
        "sold": len(disappeared_ids),
    }
