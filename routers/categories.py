from collections import Counter

from fastapi import APIRouter

from scraper.analyzer import translate_category
from scraper.marktplaats import supabase
from scraper.run import DEFAULT_KEYWORDS

router = APIRouter()


@router.get("/api/categories")
def list_categories():
    # Only aggregate curated/tracked keywords, not every one-off organic or test search -
    # keeps category browse pages showing intentional coverage (e.g. car brands) rather than
    # whatever hyper-specific term a customer happened to search once (still fully visible via
    # direct search on results.html, just not surfaced on the curated category pages).
    rows = (
        supabase.table("listings")
        .select("url, keyword")
        .eq("status", "active")
        .in_("keyword", DEFAULT_KEYWORDS)
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
