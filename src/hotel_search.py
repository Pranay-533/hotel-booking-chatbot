"""
hotel_search.py  –  Booking.com API (booking-com15.p.rapidapi.com)

Flow:
  1. get_dest_id(city)  →  calls /api/v1/hotels/searchDestination
  2. search_hotels(city) → calls get_dest_id(), then /api/v1/hotels/searchHotels
                            returns {"result": [...normalized hotels...]}
"""

import re
import requests
from datetime import datetime, timedelta


# ──────────────────────────────────────────────
# Step 1 – City  →  dest_id
# ──────────────────────────────────────────────

def get_dest_id(city: str, rapidapi_key: str, rapidapi_host: str) -> dict | None:
    """
    Translate a city name into a Booking.com dest_id.
    Returns {"dest_id": ..., "search_type": ...} or None on failure.
    """
    url = f"https://{rapidapi_host}/api/v1/hotels/searchDestination"
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": rapidapi_host,
    }
    params = {"query": city}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = data.get("data", [])
        if not results:
            return None

        # Prefer a CITY type match
        city_result = next(
            (r for r in results if r.get("search_type") == "city"),
            results[0]
        )
        return {
            "dest_id": city_result.get("dest_id"),
            "search_type": city_result.get("search_type", "city"),
        }

    except Exception as e:
        print(f"[hotel_search] get_dest_id error: {e}")
        return None


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _parse_price(raw) -> float | None:
    """Extract a numeric price from various formats."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        digits = re.sub(r"[^\d.]", "", raw)
        try:
            return float(digits) if digits else None
        except ValueError:
            return None
    return None


def _parse_rating(raw) -> float | None:
    """Extract a numeric rating safely."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, dict):
        try:
            return float(raw.get("score", 0) or raw.get("rating", 0) or 0) or None
        except (ValueError, TypeError):
            return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _normalize_hotel(h: dict) -> dict:
    """
    Flatten a raw Booking.com property dict into the shape the rest of
    the chatbot expects.
    """
    # Try multiple price paths
    price = None
    price_fmt = "Price unavailable"
    
    # Path 1: property.priceBreakdown.grossPrice
    pb = h.get("property", {}).get("priceBreakdown", {})
    gross = pb.get("grossPrice", {})
    if gross:
        price = _parse_price(gross.get("value"))
        price_fmt = gross.get("currency", "INR") + " " + str(int(price)) if price else "Price unavailable"
    
    # Path 2: direct price fields
    if price is None:
        price = _parse_price(h.get("min_total_price") or h.get("price") or h.get("composite_price_breakdown", {}).get("gross_amount_per_night", {}).get("value"))
    
    if price is None:
        price = _parse_price(h.get("property", {}).get("price"))
    
    if price and price_fmt == "Price unavailable":
        currency = h.get("property", {}).get("currency", "INR")
        price_fmt = f"{currency} {int(price)}"

    # Rating
    rating = _parse_rating(
        h.get("property", {}).get("reviewScore") 
        or h.get("review_score") 
        or h.get("property", {}).get("reviewScoreWord")
    )

    # Name
    name = (
        h.get("property", {}).get("name") 
        or h.get("hotel_name") 
        or h.get("name", "Unknown Hotel")
    )

    # Address / location
    address = h.get("property", {}).get("wishlistName") or h.get("address") or None

    # Distance
    dist_str = h.get("property", {}).get("distanceFromCenter")
    distance = None
    if dist_str:
        d_match = re.search(r"([\d.]+)", str(dist_str))
        if d_match:
            distance = float(d_match.group(1))

    return {
        "hotel_name": name,
        "review_score": rating,
        "min_total_price": price,
        "price_formatted": price_fmt,
        "currencycode": h.get("property", {}).get("currency", "INR"),
        "address": address,
        "accommodation_type_name": h.get("property", {}).get("propertyType", "Hotel"),
        "distance": distance,
        "hotel_id": h.get("property", {}).get("id") or h.get("hotel_id"),
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
    Search for hotels in *city* using the Booking.com API.

    Returns
    -------
    {"result": [<normalized hotel dicts>]}          on success
    {"error": "<message>", "result": []}            on failure
    """
    # Default dates: tomorrow → day after
    today = datetime.today()
    if not checkin_date:
        checkin_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if not checkout_date:
        checkout_date = (today + timedelta(days=2)).strftime("%Y-%m-%d")

    # ── Step 1: resolve city → dest_id
    dest_info = get_dest_id(city, rapidapi_key, rapidapi_host)
    if not dest_info:
        return {
            "error": f"Could not find a region for '{city}'. Try a different city name.",
            "result": [],
        }

    # ── Step 2: search hotels
    url = f"https://{rapidapi_host}/api/v1/hotels/searchHotels"
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": rapidapi_host,
    }
    params = {
        "dest_id": dest_info["dest_id"],
        "search_type": dest_info["search_type"],
        "arrival_date": checkin_date,
        "departure_date": checkout_date,
        "adults": str(adults_number),
        "room_qty": "1",
        "page_number": "1",
        "units": "metric",
        "temperature_unit": "c",
        "languagecode": "en-us",
        "currency_code": "INR",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        raw_hotels = data.get("data", {}).get("hotels", [])
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