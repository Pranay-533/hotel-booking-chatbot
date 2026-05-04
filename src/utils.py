"""
utils.py  –  Filtering and sorting helpers for hotel results.

Works with the normalized hotel dicts produced by hotel_search.search_hotels():
  {
      "hotel_name":             str,
      "review_score":           float | None,
      "min_total_price":        float | None,
      "price_formatted":        str,
      "currencycode":           str,
      "address":                str | None,
      "accommodation_type_name": str,
      "distance":               None,   ← Hotels.com v3 API does not supply this
      "hotel_id":               str,
  }
"""

from __future__ import annotations


# ──────────────────────────────────────────────────────────────
# Sorting
# ──────────────────────────────────────────────────────────────

def sort_by_price(hotels: list[dict]) -> list[dict]:
    """Return hotels sorted lowest price first. Hotels with no price go last."""
    return sorted(
        hotels,
        key=lambda h: (h.get("min_total_price") is None, h.get("min_total_price") or 0),
    )


def sort_by_rating(hotels: list[dict]) -> list[dict]:
    """Return hotels sorted highest rating first. Hotels with no rating go last."""
    return sorted(
        hotels,
        key=lambda h: (h.get("review_score") is None, -(h.get("review_score") or 0)),
    )


# ──────────────────────────────────────────────────────────────
# Filtering
# ──────────────────────────────────────────────────────────────

def filter_by_price(hotels: list[dict], min_price: float, max_price: float) -> list[dict]:
    """Return only hotels whose price falls within [min_price, max_price]."""
    results = []
    for h in hotels:
        price = h.get("min_total_price")
        if price is not None and min_price <= price <= max_price:
            results.append(h)
    return results


def filter_by_rating(hotels: list[dict], min_rating: float) -> list[dict]:
    """Return only hotels whose guest rating is >= min_rating."""
    return [
        h for h in hotels
        if (h.get("review_score") or 0) >= min_rating
    ]


def filter_by_distance(hotels: list[dict], max_km: float) -> list[dict]:
    """
    Return only hotels within max_km kilometres of the city centre.

    NOTE: The Hotels.com Provider v3 API does not return distance data, so
    the 'distance' field is always None. This filter will return *all* hotels
    and print a warning rather than silently returning an empty list.
    """
    filtered = [
        h for h in hotels
        if h.get("distance") is not None and h["distance"] <= max_km
    ]
    if not filtered:
        print(
            f"[utils] ⚠️  Distance filter (≤ {max_km} km) could not be applied — "
            "the Hotels.com API does not provide distance data. Showing all results instead."
        )
        return hotels
    return filtered


# ──────────────────────────────────────────────────────────────
# Display helper
# ──────────────────────────────────────────────────────────────

def format_hotel(h: dict, index: int | None = None) -> str:
    """Return a human-readable string for a single hotel."""
    prefix = f"{index}. " if index is not None else ""
    name = h.get("hotel_name", "Unknown")
    rating = h.get("review_score")
    rating_str = f"{rating:.1f}/10" if rating is not None else "No rating"
    price = h.get("price_formatted") or (
        f"₹{h['min_total_price']:.0f}" if h.get("min_total_price") else "Price unavailable"
    )
    address = h.get("address") or "Location not specified"
    return (
        f"{prefix}🏨 {name}\n"
        f"   ⭐ Rating : {rating_str}\n"
        f"   💰 Price  : {price} / night\n"
        f"   📍 Area   : {address}"
    )


def format_hotel_list(hotels: list[dict], limit: int = 5) -> str:
    """Return a formatted list of up to *limit* hotels."""
    if not hotels:
        return "No hotels found matching your criteria."
    shown = hotels[:limit]
    lines = [format_hotel(h, i + 1) for i, h in enumerate(shown)]
    remaining = len(hotels) - len(shown)
    if remaining > 0:
        lines.append(f"\n…and {remaining} more hotel(s). Ask me to filter or sort to narrow results.")
    return "\n\n".join(lines)