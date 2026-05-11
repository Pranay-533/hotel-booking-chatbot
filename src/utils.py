"""
utils.py  –  Filtering, sorting, and display helpers for hotel results.

Works with the normalized hotel dicts produced by hotel_search.search_hotels():
  {
      "hotel_name":             str,
      "review_score":           float | None,   (star rating 1-5)
      "min_total_price":        float | None,
      "price_formatted":        str,
      "currencycode":           str,
      "address":                str | None,
      "accommodation_type_name": str,
      "distance":               float | None,   (km from city center)
      "hotel_id":               str,
      "phone":                  str | None,
      "website":                str | None,
      "email":                  str | None,
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


def sort_by_distance(hotels: list[dict]) -> list[dict]:
    """Return hotels sorted nearest first."""
    return sorted(
        hotels,
        key=lambda h: (h.get("distance") is None, h.get("distance") or 999),
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
    """Return only hotels whose star rating is >= min_rating."""
    return [
        h for h in hotels
        if (h.get("review_score") or 0) >= min_rating
    ]


def filter_by_distance(hotels: list[dict], max_km: float) -> list[dict]:
    """Return only hotels within max_km kilometres of the city centre."""
    filtered = [
        h for h in hotels
        if h.get("distance") is not None and h["distance"] <= max_km
    ]
    if not filtered:
        return hotels  # Return all if none match
    return filtered


# ──────────────────────────────────────────────────────────────
# Display helpers
# ──────────────────────────────────────────────────────────────

def format_hotel(h: dict, index: int | None = None) -> str:
    """Return a human-readable string for a single hotel with contact details."""
    prefix = f"{index}. " if index is not None else ""
    name = h.get("hotel_name", "Unknown")
    
    # Star rating
    rating = h.get("review_score")
    if rating is not None:
        stars = "⭐" * int(rating)
        rating_str = f"{stars} ({rating}/5)"
    else:
        rating_str = "Not rated"
    
    # Type
    htype = h.get("accommodation_type_name", "Hotel")
    
    # Distance
    dist = h.get("distance")
    dist_str = f"{dist} km from center" if dist is not None else "Distance unknown"
    
    # Address
    address = h.get("address") or "Address not available"
    
    # Contact info
    phone = h.get("phone")
    website = h.get("website")
    email = h.get("email")
    
    lines = [
        f"{prefix}🏨 **{name}** ({htype})",
        f"   ⭐ Rating   : {rating_str}",
        f"   📍 Distance : {dist_str}",
        f"   🗺️ Address  : {address}",
    ]
    
    if phone:
        lines.append(f"   📞 Phone    : {phone}")
    if website:
        lines.append(f"   🌐 Website  : {website}")
    if email:
        lines.append(f"   📧 Email    : {email}")
    
    if not phone and not website and not email:
        lines.append(f"   ℹ️ Contact  : Search '{name}' on Google Maps for booking details")
    
    return "\n".join(lines)


def format_hotel_list(hotels: list[dict], limit: int = 5) -> str:
    """Return a formatted list of up to *limit* hotels."""
    if not hotels:
        return "No hotels found matching your criteria."
    shown = hotels[:limit]
    lines = [format_hotel(h, i + 1) for i, h in enumerate(shown)]
    remaining = len(hotels) - len(shown)
    if remaining > 0:
        lines.append(f"\n…and **{remaining} more** hotel(s). Say 'show more' to see more results, or filter/sort to narrow down!")
    return "\n\n".join(lines)