"""Deal score calculation and listing enrichment (category/price-type translation, warning flags)."""

# Marktplaats' top-level category taxonomy (slug -> Dutch name), taken from the site's own
# navigation config. The search API only returns a numeric categoryId with no name, so we
# derive the readable group from the URL slug instead of hand-mapping thousands of leaf ids.
TOP_LEVEL_CATEGORIES = {
    "antiek-en-kunst": "Antiek en Kunst",
    "audio-tv-en-foto": "Audio, Tv en Foto",
    "auto-kopen": "Auto's",
    "auto-onderdelen": "Auto-onderdelen",
    "auto-diversen": "Auto diversen",
    "boeken": "Boeken",
    "caravans-en-kamperen": "Caravans en Kamperen",
    "cd-s-en-dvd-s": "Cd's en Dvd's",
    "computers-en-software": "Computers en Software",
    "contacten-en-berichten": "Contacten en Berichten",
    "diensten-en-vakmensen": "Diensten en Vakmensen",
    "dieren-en-toebehoren": "Dieren en Toebehoren",
    "doe-het-zelf-en-verbouw": "Doe-het-zelf en Verbouw",
    "fietsen-en-brommers": "Fietsen en Brommers",
    "hobby-en-vrije-tijd": "Hobby en Vrije tijd",
    "huis-en-inrichting": "Huis en Inrichting",
    "huizen-en-kamers": "Huizen en Kamers",
    "kinderen-en-baby-s": "Kinderen en Baby's",
    "kleding-dames": "Kleding | Dames",
    "kleding-heren": "Kleding | Heren",
    "motoren": "Motoren",
    "muziek-en-instrumenten": "Muziek en Instrumenten",
    "postzegels-en-munten": "Postzegels en Munten",
    "sieraden-tassen-en-uiterlijk": "Sieraden, Tassen en Uiterlijk",
    "spelcomputers-en-games": "Spelcomputers en Games",
    "sport-en-fitness": "Sport en Fitness",
    "telecommunicatie": "Telecommunicatie",
    "tickets-en-kaartjes": "Tickets en Kaartjes",
    "tuin-en-terras": "Tuin en Terras",
    "vacatures": "Vacatures",
    "vakantie": "Vakantie",
    "verzamelen": "Verzamelen",
    "watersport-en-boten": "Watersport en Boten",
    "witgoed-en-apparatuur": "Witgoed en Apparatuur",
    "zakelijke-goederen": "Zakelijke goederen",
    "diversen": "Diversen",
}

# Real values observed from Marktplaats' priceInfo.priceType (not the Dutch labels the
# original spec assumed). MIN_BID/FAST_BID are both auction-style ("Bieden") listings.
PRICE_TYPE_LABELS = {
    "FIXED": "Vaste prijs",
    "MIN_BID": "Bieden vanaf",
    "FAST_BID": "Bieden",
    "NOTK": "Prijs op aanvraag",
    "SEE_DESCRIPTION": "Zie beschrijving",
}
BIDDING_PRICE_TYPES = {"MIN_BID", "FAST_BID"}

SCAM_KEYWORDS = ("whatsapp", "western union")


def _url_slugs(url: str | None) -> tuple[str | None, str | None]:
    if not url:
        return None, None
    parts = [p for p in url.split("/") if p]
    if "v" not in parts:
        return None, None
    idx = parts.index("v")
    top = parts[idx + 1] if len(parts) > idx + 1 else None
    sub = parts[idx + 2] if len(parts) > idx + 2 else None
    return top, sub


def translate_category(url: str | None) -> dict:
    """Derive a Dutch (group, name) pair from a Marktplaats listing URL's slug."""
    top, sub = _url_slugs(url)
    group = TOP_LEVEL_CATEGORIES.get(top) if top else None
    if not group:
        group = top.replace("-", " ").capitalize() if top else "Overig"
    name = sub.replace("-", " ").capitalize() if sub else group
    return {"group": group, "name": name}


def translate_price_type(price_type: str | None) -> str | None:
    if not price_type:
        return None
    return PRICE_TYPE_LABELS.get(price_type, price_type)


def calculate_deal_score(price: float | None, median_price: float | None) -> tuple[str | None, float | None]:
    """Returns (label, discount_percent). discount_percent > 0 means cheaper than median."""
    if not price or not median_price:
        return None, None

    difference = (median_price - price) / median_price * 100
    if difference > 20:
        label = "\U0001f7e2 Goede deal"
    elif difference > 5:
        label = "\U0001f7e1 Gemiddeld"
    elif difference < -15:
        label = "\U0001f534 Te duur"
    else:
        label = "\U0001f7e1 Gemiddeld"
    return label, round(difference, 1)


def get_flags(
    *,
    price: float | None,
    seller_type: str | None,
    days_listed: int | None,
    price_type: str | None,
    median_price: float | None,
    description: str | None = None,
) -> dict:
    negotiation_tip = bool(days_listed and days_listed > 14)
    bidding = price_type in BIDDING_PRICE_TYPES

    scam_warning = bool(
        seller_type == "particulier"
        and price
        and median_price
        and price < median_price * 0.4
    )
    if description:
        lowered = description.lower()
        if any(term in lowered for term in SCAM_KEYWORDS):
            scam_warning = True

    return {
        "negotiation_tip": negotiation_tip,
        "scam_warning": scam_warning,
        "bidding": bidding,
    }


def analyze_listing(listing: dict, median_price: float | None, description: str | None = None) -> dict:
    """Enriches a stored/scraped listing dict with deal score, category and flags."""
    deal_score, discount_percent = calculate_deal_score(listing.get("price"), median_price)
    category_info = translate_category(listing.get("url"))
    flags = get_flags(
        price=listing.get("price"),
        seller_type=listing.get("seller_type"),
        days_listed=listing.get("days_listed"),
        price_type=listing.get("price_type"),
        median_price=median_price,
        description=description,
    )

    return {
        **listing,
        "deal_score": deal_score,
        "discount_percent": discount_percent,
        "median_price": median_price,
        "price_type_label": translate_price_type(listing.get("price_type")),
        "category_group": category_info["group"],
        "category_name": category_info["name"],
        **flags,
    }
