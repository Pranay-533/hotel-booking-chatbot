"""
hotel_search.py  –  Hotel search using OpenCage Geocoding + Overpass API (OpenStreetMap)

Flow:
  1. get_coordinates(city) → Uses OpenCage to convert city name to lat/lon
  2. search_hotels(city)   → Uses Overpass API to find hotels near those coordinates
                              Returns {"result": [...normalized hotels...]}

Overpass API is completely FREE with no API key required.
It queries OpenStreetMap data which includes hotel names, addresses,
phone numbers, websites, star ratings, and more.
"""

import re
import requests
import math
from src.coordinates import get_coordinates


# ──────────────────────────────────────────────
# Overpass API – query OpenStreetMap for hotels
# ──────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _query_overpass(lat: float, lon: float, radius_m: int = 15000) -> list[dict]:
    """
    Query Overpass API for hotels, guest houses, motels, and resorts
    within `radius_m` metres of (lat, lon).
    """
    query = (
        f'[out:json][timeout:25];'
        f'('
        f'node["tourism"="hotel"](around:{radius_m},{lat},{lon});'
        f'way["tourism"="hotel"](around:{radius_m},{lat},{lon});'
        f'node["tourism"="guest_house"](around:{radius_m},{lat},{lon});'
        f'way["tourism"="guest_house"](around:{radius_m},{lat},{lon});'
        f'node["tourism"="motel"](around:{radius_m},{lat},{lon});'
        f'way["tourism"="motel"](around:{radius_m},{lat},{lon});'
        f');out center body;'
    )

    headers = {
        "User-Agent": "HotelBot/1.0 (hotel booking chatbot)",
        "Accept": "application/json",
    }

    # Try primary and fallback Overpass servers
    servers = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]

    for server_url in servers:
        try:
            response = requests.get(
                server_url,
                params={"data": query},
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            elements = data.get("elements", [])
            if elements:
                return elements
        except Exception as e:
            print(f"[hotel_search] Overpass API error ({server_url}): {e}")
            continue

    return []


# ──────────────────────────────────────────────
# Distance calculation (Haversine)
# ──────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two lat/lon points."""
    R = 6371  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ──────────────────────────────────────────────
# Normalize OSM data into our hotel format
# ──────────────────────────────────────────────

def _parse_stars(tags: dict) -> float | None:
    """Extract star rating from OSM tags."""
    stars = tags.get("stars")
    if stars:
        m = re.search(r"(\d+(?:\.\d+)?)", str(stars))
        if m:
            return float(m.group(1))
    star_rating = tags.get("star_rating")
    if star_rating:
        try:
            return float(star_rating)
        except ValueError:
            pass
    return None


def _normalize_hotel(element: dict, city_lat: float, city_lon: float) -> dict:
    """Convert an OSM element into the chatbot's standard hotel dict."""
    tags = element.get("tags", {})

    # Get coordinates (node has lat/lon directly; way has center)
    lat = element.get("lat") or element.get("center", {}).get("lat")
    lon = element.get("lon") or element.get("center", {}).get("lon")

    # Calculate distance from city center
    distance = None
    if lat and lon:
        distance = round(_haversine_km(city_lat, city_lon, lat, lon), 1)

    # Build address
    addr_parts = []
    for key in ["addr:street", "addr:housenumber", "addr:suburb", "addr:city", "addr:postcode"]:
        val = tags.get(key)
        if val:
            addr_parts.append(val)
    address = ", ".join(addr_parts) if addr_parts else tags.get("addr:full", None)

    # Phone & website
    phone = tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile")
    website = tags.get("website") or tags.get("contact:website") or tags.get("url")
    email = tags.get("email") or tags.get("contact:email")

    # Star rating
    stars = _parse_stars(tags)

    # Tourism type
    tourism_type = tags.get("tourism", "hotel").replace("_", " ").title()

    return {
        "hotel_name": tags.get("name", "Unnamed Hotel"),
        "review_score": stars,  # OSM star rating (1-5 scale)
        "min_total_price": None,  # OSM doesn't have price data
        "price_formatted": "Contact hotel for pricing",
        "currencycode": "INR",
        "address": address,
        "accommodation_type_name": tourism_type,
        "distance": distance,
        "hotel_id": element.get("id"),
        "phone": phone,
        "website": website,
        "email": email,
        "lat": lat,
        "lon": lon,
    }


# ──────────────────────────────────────────────
# Main search entry point
# ──────────────────────────────────────────────

def search_hotels(
    city: str,
    opencage_key: str,
    _unused_host: str = "",
    checkin_date: str | None = None,
    checkout_date: str | None = None,
    adults_number: int = 2,
) -> dict:
    """
    Search for hotels in *city* using OpenCage geocoding + Overpass API.

    Parameters
    ----------
    city          : e.g. "Delhi", "Mumbai", "Jalandhar"
    opencage_key  : OpenCage API key for geocoding

    Returns
    -------
    {"result": [<normalized hotel dicts>]}          on success
    {"error": "<message>", "result": []}            on failure
    """
    # Step 1: Geocode the city
    lat, lon = get_coordinates(city, opencage_key)
    if lat is None or lon is None:
        return {
            "error": f"Could not find location '{city}'. Please check the city name and try again.",
            "result": [],
        }

    # Step 2: Query Overpass for hotels
    raw_hotels = _query_overpass(lat, lon, radius_m=15000)

    if not raw_hotels:
        # Try with a larger radius
        raw_hotels = _query_overpass(lat, lon, radius_m=30000)

    if not raw_hotels:
        return {
            "error": f"No hotels found near '{city}'. Try a larger city or different spelling.",
            "result": [],
        }

    # Normalize and filter out unnamed hotels
    normalized = []
    for h in raw_hotels:
        hotel = _normalize_hotel(h, lat, lon)
        if hotel["hotel_name"] != "Unnamed Hotel":
            normalized.append(hotel)

    # If all are unnamed, include them anyway
    if not normalized:
        normalized = [_normalize_hotel(h, lat, lon) for h in raw_hotels]

    # Sort by distance from city center
    normalized.sort(key=lambda h: h.get("distance") or 999)

    return {"result": normalized}