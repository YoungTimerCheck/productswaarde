import os
import random
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.marktplaats import scrape_marktplaats, store_listings, supabase

DEFAULT_KEYWORDS = [
    "iphone 13", "iphone 14", "samsung galaxy s23",
    "playstation 5", "nintendo switch", "macbook air",
    "elektrische fiets", "racefiets", "laptop",
    "canon camera", "sony camera", "airpods",
    "ipad", "dyson stofzuiger", "espressomachine",
]


def get_queue_keywords() -> list[str]:
    rows = supabase.table("scraper_queue").select("keyword").eq("active", True).execute().data
    return [row["keyword"] for row in rows]


def resolve_keywords() -> list[str]:
    return sorted(set(DEFAULT_KEYWORDS) | set(get_queue_keywords()))


def run(keywords: list[str]) -> None:
    now = datetime.now(timezone.utc).isoformat()

    for i, keyword in enumerate(keywords):
        print(f"Scraping '{keyword}'...")
        try:
            listings = scrape_marktplaats(keyword)
            result = store_listings(keyword, listings)
            print(
                f"  fetched {result['fetched']} | "
                f"+{result['new']} new, {result['updated']} updated, {result['sold']} marked sold"
            )
            supabase.table("scraper_queue").upsert(
                {"keyword": keyword, "last_scraped": now, "active": True},
                on_conflict="keyword",
            ).execute()
        except Exception as exc:
            print(f"  error scraping '{keyword}': {exc}")

        if i < len(keywords) - 1:
            time.sleep(random.uniform(2, 3))


if __name__ == "__main__":
    run(sys.argv[1:] or resolve_keywords())
