from collections import Counter

from fastapi import APIRouter

from scraper.analyzer import translate_category
from scraper.marktplaats import supabase

router = APIRouter()


@router.get("/api/categories")
def list_categories():
    rows = (
        supabase.table("listings")
        .select("url, keyword")
        .eq("status", "active")
        .execute()
        .data
    )

    counts = Counter()
    keywords_by_group: dict[str, set] = {}
    for row in rows:
        group = translate_category(row["url"])["group"]
        counts[group] += 1
        keywords_by_group.setdefault(group, set()).add(row["keyword"])

    categories = [
        {
            "name": group,
            "active_listings": count,
            "keywords": sorted(keywords_by_group[group]),
        }
        for group, count in counts.most_common()
    ]

    return {"categories": categories}
