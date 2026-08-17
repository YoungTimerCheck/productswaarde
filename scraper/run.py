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
    # Top ~20 car brands (Netherlands market) - curated coverage for the "Auto's" category,
    # rather than relying on whatever one-off model/engine-variant a customer happens to search.
    "volkswagen", "opel", "peugeot", "renault", "toyota",
    "ford", "kia", "hyundai", "skoda", "bmw",
    "audi", "mercedes-benz", "citroen", "volvo", "nissan",
    "fiat", "mazda", "seat", "mini", "dacia",
    # Meubels - previously had zero curated coverage.
    "bank", "eettafel", "bureau", "boekenkast",
    "kledingkast", "salontafel", "ledikant", "dressoir",
    # Kleding - previously had zero curated coverage; clothing/footwear on Marktplaats is
    # searched by brand far more than by generic garment type.
    "nike", "adidas", "zara", "north face",
    "levi's", "carhartt", "ralph lauren", "uggs",
    # Fietsen en Brommers - topping up from 2 keywords (elektrische fiets, racefiets).
    "mountainbike", "stadsfiets", "gazelle", "batavus",
    "vouwfiets", "kinderfiets",
    # Audio, Tv en Foto - topping up from 3 (airpods, canon camera, sony camera).
    "koptelefoon", "bluetooth speaker", "gopro",
    "platenspeler", "nikon camera", "fujifilm camera",
    # Witgoed en Apparatuur - topping up from 2 (dyson stofzuiger, espressomachine).
    "wasmachine", "koelkast", "vaatwasser",
    "airfryer", "magnetron", "droger",
    # Computers en Software - topping up (laptop/macbook air already covered general laptops).
    "computerscherm", "gaming laptop", "chromebook",
    "dell laptop", "hp laptop",
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
            listings = scrape_marktplaats(keyword, pages=3)
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
