"""
app.py  –  Flask API backend for the Hotel Booking Chatbot.

Deployed on Render. Serves JSON API only (no HTML templates).
Frontend is deployed separately on Vercel.
"""

import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from src.hotel_search import search_hotels
from src.utils import (
    sort_by_price,
    sort_by_rating,
    filter_by_price,
    filter_by_rating,
    filter_by_distance,
    format_hotel_list,
    format_hotel,
)

load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for Vercel frontend

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "hotels-com-provider.p.rapidapi.com")

# ── Per-session state (in-memory; resets on server restart) ────
_session = {
    "hotels": [],
    "last_city": None,
}


# ── Intent helpers (same as main.py) ──────────────────────────

def extract_city(text: str) -> str | None:
    m = re.search(r"hotels?\s+in\s+([a-zA-Z\s]+)", text, re.IGNORECASE)
    return m.group(1).strip().title() if m else None


def extract_price_range(text: str) -> tuple[float, float] | None:
    m = re.search(r"between\s+(\d+)\s+and\s+(\d+)", text, re.IGNORECASE)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"under\s+(\d+)", text, re.IGNORECASE)
    if m:
        return 0.0, float(m.group(1))
    m = re.search(r"above\s+(\d+)", text, re.IGNORECASE)
    if m:
        return float(m.group(1)), float("inf")
    return None


def extract_rating(text: str) -> float | None:
    m = re.search(r"rating\s+(?:above|over|min(?:imum)?|>=?|at\s+least)?\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def extract_distance(text: str) -> float | None:
    m = re.search(r"within\s+(\d+(?:\.\d+)?)\s*km", text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def find_hotel_by_name(name_fragment: str) -> dict | None:
    for h in _session["hotels"]:
        if name_fragment.lower() in h["hotel_name"].lower():
            return h
    return None


# ── Core handler ───────────────────────────────────────────────

def handle_message(user_input: str) -> str:
    text = user_input.strip().lower()
    
    if not RAPIDAPI_KEY:
        return "❌ Error: API Key missing! You need to add `RAPIDAPI_KEY` to your Vercel Environment Variables and redeploy."

    # Hotel search
    city = extract_city(user_input)
    if city:
        result = search_hotels(city, RAPIDAPI_KEY, RAPIDAPI_HOST)
        if result.get("error"):
            return f"❌ {result['error']}"
        _session["hotels"] = result["result"]
        _session["last_city"] = city
        return (
            f"🏙️ Found {len(_session['hotels'])} hotels in {city}. Here are the top results:\n\n"
            + format_hotel_list(_session["hotels"])
        )

    if not _session["hotels"]:
        return "Please search for hotels first, e.g. 'hotels in Mumbai'."

    # Sorting
    if "sort by price" in text or "cheapest" in text:
        _session["hotels"] = sort_by_price(_session["hotels"])
        return "✅ Sorted by price:\n\n" + format_hotel_list(_session["hotels"])

    if "sort by rating" in text or "best rated" in text:
        _session["hotels"] = sort_by_rating(_session["hotels"])
        return "✅ Sorted by rating:\n\n" + format_hotel_list(_session["hotels"])

    # Price filter
    price_range = extract_price_range(text)
    if price_range:
        lo, hi = price_range
        filtered = filter_by_price(_session["hotels"], lo, hi)
        if not filtered:
            return f"No hotels found between ₹{lo:.0f} and ₹{hi:.0f}."
        _session["hotels"] = filtered
        return f"✅ {len(filtered)} hotel(s) found:\n\n" + format_hotel_list(filtered)

    # Rating filter
    min_rating = extract_rating(text)
    if min_rating is not None:
        filtered = filter_by_rating(_session["hotels"], min_rating)
        if not filtered:
            return f"No hotels with rating ≥ {min_rating}."
        _session["hotels"] = filtered
        return f"✅ {len(filtered)} hotel(s):\n\n" + format_hotel_list(filtered)

    # Distance filter
    max_km = extract_distance(text)
    if max_km is not None:
        filtered = filter_by_distance(_session["hotels"], max_km)
        _session["hotels"] = filtered
        return f"✅ Hotels within {max_km} km:\n\n" + format_hotel_list(filtered)

    # Detail view
    if "tell me more" in text or "details" in text or "about" in text:
        m = re.search(r"about\s+(.+)", user_input, re.IGNORECASE)
        if m:
            hotel = find_hotel_by_name(m.group(1).strip())
            if hotel:
                return format_hotel(hotel)
        return "Please specify the hotel name, e.g. 'tell me more about Taj Hotel'."

    if "show more" in text or "more results" in text:
        return format_hotel_list(_session["hotels"], limit=10)

    return (
        "I can help you find hotels! Try:\n"
        "  • 'hotels in Delhi'\n"
        "  • 'sort by rating'\n"
        "  • 'price between 500 and 2000'\n"
        "  • 'tell me more about [hotel name]'"
    )


# ── Flask routes ───────────────────────────────────────────────

@app.route("/")
def index():
    return jsonify({"status": "ok", "service": "HotelBot API", "endpoints": ["/chat", "/health"]})


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"reply": "Please type a message."})
    reply = handle_message(user_message)
    return jsonify({"reply": reply})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)