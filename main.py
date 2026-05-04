"""
main.py  –  CLI chatbot entry point for the Hotel Booking Chatbot.

Usage:
    python main.py
"""

import os
import re
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

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "hotels-com-provider.p.rapidapi.com")


# ── Session state ──────────────────────────────────────────────
session = {
    "hotels": [],       # current list of normalized hotel dicts
    "last_city": None,  # last searched city
}


# ── Intent helpers ─────────────────────────────────────────────

def extract_city(text: str) -> str | None:
    """Pull a city name from phrases like 'hotels in Delhi'."""
    m = re.search(r"hotels?\s+in\s+([a-zA-Z\s]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip().title()
    return None


def extract_price_range(text: str) -> tuple[float, float] | None:
    """Pull min/max from 'price between 500 and 2000' or 'under 1500'."""
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
    """Pull a minimum rating value from 'rating above 7' etc."""
    m = re.search(r"rating\s+(?:above|over|min(?:imum)?|>=?|at\s+least)?\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def extract_distance(text: str) -> float | None:
    """Pull km from 'within 5 km'."""
    m = re.search(r"within\s+(\d+(?:\.\d+)?)\s*km", text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def find_hotel_by_name(name_fragment: str) -> dict | None:
    """Return the first hotel whose name contains name_fragment (case-insensitive)."""
    for h in session["hotels"]:
        if name_fragment.lower() in h["hotel_name"].lower():
            return h
    return None


# ── Response builder ───────────────────────────────────────────

def handle_message(user_input: str) -> str:
    text = user_input.strip().lower()

    # ── Hotel search ────────────────────────────────────────────
    city = extract_city(user_input)
    if city:
        print(f"🔍 Searching for hotels in {city}…")
        result = search_hotels(city, RAPIDAPI_KEY, RAPIDAPI_HOST)
        if result.get("error"):
            return f"❌ {result['error']}"
        session["hotels"] = result["result"]
        session["last_city"] = city
        return (
            f"🏙️  Found {len(session['hotels'])} hotels in {city}. "
            f"Here are the top results:\n\n"
            + format_hotel_list(session["hotels"])
        )

    # ── Sorting ──────────────────────────────────────────────────
    if not session["hotels"]:
        return "Please search for hotels first, e.g. 'hotels in Mumbai'."

    if "sort by price" in text or "cheapest" in text:
        session["hotels"] = sort_by_price(session["hotels"])
        return "✅ Sorted by price (lowest first):\n\n" + format_hotel_list(session["hotels"])

    if "sort by rating" in text or "best rated" in text:
        session["hotels"] = sort_by_rating(session["hotels"])
        return "✅ Sorted by rating (highest first):\n\n" + format_hotel_list(session["hotels"])

    # ── Filtering ────────────────────────────────────────────────
    price_range = extract_price_range(text)
    if price_range:
        lo, hi = price_range
        filtered = filter_by_price(session["hotels"], lo, hi)
        if not filtered:
            return f"No hotels found with price between ₹{lo:.0f} and ₹{hi:.0f}."
        session["hotels"] = filtered
        return f"✅ {len(filtered)} hotel(s) in price range:\n\n" + format_hotel_list(filtered)

    min_rating = extract_rating(text)
    if min_rating is not None:
        filtered = filter_by_rating(session["hotels"], min_rating)
        if not filtered:
            return f"No hotels with rating ≥ {min_rating}."
        session["hotels"] = filtered
        return f"✅ {len(filtered)} hotel(s) with rating ≥ {min_rating}:\n\n" + format_hotel_list(filtered)

    max_km = extract_distance(text)
    if max_km is not None:
        filtered = filter_by_distance(session["hotels"], max_km)
        session["hotels"] = filtered
        return f"✅ Hotels within {max_km} km:\n\n" + format_hotel_list(filtered)

    # ── Hotel detail ─────────────────────────────────────────────
    if "tell me more" in text or "details" in text or "about" in text:
        # Try to extract hotel name after "about"
        m = re.search(r"about\s+(.+)", user_input, re.IGNORECASE)
        if m:
            hotel = find_hotel_by_name(m.group(1).strip())
            if hotel:
                return "Here are the details:\n\n" + format_hotel(hotel)
        return "Please specify the hotel name, e.g. 'tell me more about Taj Hotel'."

    # ── Show more ────────────────────────────────────────────────
    if "show more" in text or "more results" in text:
        return format_hotel_list(session["hotels"], limit=10)

    # ── Fallback ─────────────────────────────────────────────────
    return (
        "I can help you find hotels! Try:\n"
        "  • 'hotels in Delhi'\n"
        "  • 'sort by rating'\n"
        "  • 'price between 500 and 2000'\n"
        "  • 'tell me more about [hotel name]'"
    )


# ── Main loop ──────────────────────────────────────────────────

def main():
    print("Welcome to HotelBot! Type your query or 'exit' to quit.")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "bye"}:
            print("Bot: Goodbye! Happy travels! ✈️")
            break

        response = handle_message(user_input)
        print(f"Bot: {response}\n")


if __name__ == "__main__":
    main()