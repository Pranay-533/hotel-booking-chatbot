"""
hotel_search.py  –  Hotels.com Provider API (hotels-com-provider.p.rapidapi.com)

Flow:
  1. get_region_id(city)  →  calls /v2/regions to turn a city name into a region_id
  2. search_hotels(city)  →  calls get_region_id(), then /v3/hotels/search
                              returns {"result": [...normalized hotels...]}
"""

import re
import requests
from datetime import datetime, timedelta


# ──────────────────────────────────────────────
# Step 1 – City  →  region_id
# ──────────────────────────────────────────────

def get_region_id(city: str, rapidapi_key: str, rapidapi_host: str) -> str | None:
    """
    Translate a city name into a Hotels.com region_id (gaiaId).
    Prefers a result with type == 'CITY'; falls back to the first result.
    Returns the region_id string, or None on failure.
    """
    url = f"https://{rapidapi_host}/v2/regions"
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": rapidapi_host,
    }
    params = {
        "query": city,
        "locale": "en_IN",
        "domain": "IN",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = data.get("data", [])
        if not results:
            return None

        # Prefer an exact CITY match, fall back to first result
        city_result = next(
            (r for r in results if r.get("type") == "CITY"),
            results[0]
        )
        return city_result["gaiaId"]

    except Exception as e:
        print(f"[hotel_search] get_region_id error: {e}")
        return None


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _parse_price(formatted: str) -> float | None:
    """
    Turn a formatted price string like '₹1,234' or 'INR 1234' into a float.
    Returns None if parsing fails.
    """
    if not formatted:
        return None
    # Strip everything that isn't a digit or decimal point
    digits = re.sub(r"[^\d.]", "", formatted)
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def _extract_lead_price(hotel: dict) -> tuple[float | None, str]:
    """
    Pull the LEAD (current) price from the nested price structure.
    Returns (price_float, formatted_string).
    """
    try:
        display_prices = (
            hotel["price"]["priceSummary"]["displayPrices"]
        )
        lead = next(
            (d for d in display_prices if d.get("role") == "LEAD"),
            display_prices[0] if display_prices else None,
        )
        if lead:
            fmt = lead["price"]["formatted"]
            return _parse_price(fmt), fmt
    except (KeyError, TypeError):
        pass
    return None, ""


def _parse_rating(raw) -> float | None:
    """
    The Hotels.com v3 API returns guestRating as either:
      - None / missing
      - a dict like {'rating': '5.6', 'ratingText': '5.6 out of 10', ...}
    Extract the numeric value safely.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, dict):
        try:
            return float(raw.get("rating", 0) or 0) or None
        except (ValueError, TypeError):
            return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _normalize_hotel(h: dict) -> dict:
    """
    Flatten a raw Hotels.com v3 property dict into the shape the rest of
    the chatbot expects.
    """
    price_float, price_fmt = _extract_lead_price(h)

    return {
        "hotel_name": h.get("name", "Unknown Hotel"),
        "review_score": _parse_rating(h.get("guestRating")),  # float or None
        "min_total_price": price_float,                        # float or None
        "price_formatted": price_fmt,                          # e.g. "₹1,234"
        "currencycode": "INR",
        "address": (h.get("messages") or [None])[0],          # first message = city/area
        "accommodation_type_name": "Hotel",
        "distance": None,   # v3 API does not return distance from centre
        "hotel_id": h.get("id"),
    }


# ──────────────────────────────────────────────
# Step 2 – Main search entry point
# ──────────────────────────────────────────────

def search_hotels(
    city: str,
    rapidapi_key: str,
    rapidapi_host: str,
    checkin_date: str | None = None,
    checkout_date: str | None = None,
    adults_number: int = 2,
) -> dict:
    """
    Search for hotels in *city* using the Hotels.com Provider API.

    Parameters
    ----------
    city            : e.g. "Delhi", "Mumbai"
    rapidapi_key    : your RapidAPI key
    rapidapi_host   : "hotels-com-provider.p.rapidapi.com"
    checkin_date    : "YYYY-MM-DD"  (defaults to today)
    checkout_date   : "YYYY-MM-DD"  (defaults to tomorrow)
    adults_number   : number of adult guests

    Returns
    -------
    {"result": [<normalized hotel dicts>]}          on success
    {"error": "<message>", "result": []}            on failure
    """
    # Default dates: today → tomorrow
    today = datetime.today()
    if not checkin_date:
        checkin_date = today.strftime("%Y-%m-%d")
    if not checkout_date:
        checkout_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    # ── Step 1: resolve city → region_id ──────────────────────────────
    region_id = get_region_id(city, rapidapi_key, rapidapi_host)
    if not region_id:
        return {
            "error": f"Could not find a region for '{city}'. Try a different city name.",
            "result": [],
        }

    # ── Step 2: search hotels ──────────────────────────────────────────
    url = f"https://{rapidapi_host}/v3/hotels/search"
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": rapidapi_host,
    }
    params = {
        "region_id": region_id,
        "locale": "en_IN",
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "adults_number": str(adults_number),
        "domain": "IN",
        "sort_order": "PRICE_LOW_TO_HIGH",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        raw_hotels = data.get("data", {}).get("properties", [])
        if not raw_hotels:
            return {
                "error": f"No hotels found for '{city}' on those dates.",
                "result": [],
            }

        normalized = [_normalize_hotel(h) for h in raw_hotels]
        return {"result": normalized}

    except requests.exceptions.HTTPError as e:
        return {"error": f"API HTTP error: {e}", "result": []}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Please try again.", "result": []}
    except Exception as e:
        return {"error": f"Unexpected error: {e}", "result": []}