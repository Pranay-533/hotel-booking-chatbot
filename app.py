"""
app.py  –  Flask API backend for the Hotel Booking Chatbot.

Deployed on Render. Serves JSON API only (no HTML templates).
Frontend is deployed separately on Vercel.

Uses OpenCage for geocoding and Overpass API (OpenStreetMap) for hotel data.
"""

import os
import re
import random
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from src.hotel_search import search_hotels
from src.utils import (
    sort_by_price,
    sort_by_rating,
    sort_by_distance,
    filter_by_price,
    filter_by_rating,
    filter_by_distance,
    format_hotel_list,
    format_hotel,
)

load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for Vercel frontend

OPENCAGE_KEY = os.getenv("OPENCAGE_KEY")

# ── Per-session state (in-memory; resets on server restart) ────
_session = {
    "hotels": [],
    "last_city": None,
}


# ── Conversational responses ──────────────────────────────────

GREETINGS = [
    "Hello! 👋 I'm **HotelBot**, your personal hotel booking assistant!\n\nI can help you find hotels in any city with **real contact details** — phone numbers, websites, and addresses sourced from OpenStreetMap.\n\nTry saying: **'hotels in Mumbai'** or **'find hotels in Jalandhar'** 🏨",
    "Hey there! 😊 Welcome to **HotelBot**!\n\nI search real hotel data to find nearby hotels with contact details for direct booking.\n\nJust tell me a city like **'hotels in Delhi'** or **'show me hotels in Goa'** to get started!",
    "Hi! 🙌 I'm your AI hotel assistant!\n\nI can find hotels anywhere with their **addresses, phone numbers, and websites** so you can book directly.\n\nTell me a city to explore — e.g. **'hotels in Bangalore'** ✨",
]

THANKS_RESPONSES = [
    "You're welcome! 😊 Happy to help. Need anything else? Just ask!",
    "Glad I could help! 🙌 Let me know if you need more hotel recommendations.",
    "Anytime! 😄 If you want to search for hotels in another city, just say the word!",
]

HELP_TEXT = (
    "🤖 **Here's what I can do for you:**\n\n"
    "🔍 **Search Hotels:**\n"
    "  • 'hotels in Mumbai'\n"
    "  • 'find hotels in Paris'\n"
    "  • 'show me hotels in Jalandhar'\n\n"
    "📊 **Sort Results:**\n"
    "  • 'sort by rating'\n"
    "  • 'sort by distance' or 'nearest'\n\n"
    "🔎 **Filter Results:**\n"
    "  • 'rating above 3'\n"
    "  • 'within 5 km'\n\n"
    "📋 **Hotel Details:**\n"
    "  • 'tell me more about [hotel name]'\n"
    "  • 'show more results'\n\n"
    "📞 **Contact Info:**\n"
    "  Each result shows phone numbers, websites, and addresses when available!\n\n"
    "Just type naturally and I'll understand! 😊"
)

GOODBYE_RESPONSES = [
    "Goodbye! 👋 Have a wonderful trip! Come back anytime you need hotel recommendations. 🏨✨",
    "See you later! 😊 Wishing you an amazing stay wherever you go! ✈️",
    "Bye! 🙌 Hope I helped you find something great. Safe travels! 🌍",
]


def is_greeting(text: str) -> bool:
    greetings = ["hi", "hii", "hiii", "hello", "hey", "hola", "namaste", "yo", "sup",
                 "good morning", "good afternoon", "good evening", "good night",
                 "what's up", "whats up", "howdy", "greetings"]
    return any(text.strip().lower().startswith(g) for g in greetings) or text.strip().lower() in greetings


def is_thanks(text: str) -> bool:
    thanks = ["thank", "thanks", "thx", "ty", "appreciate", "grateful", "awesome", "great job", "nice work", "perfect"]
    return any(t in text.lower() for t in thanks)


def is_goodbye(text: str) -> bool:
    goodbyes = ["bye", "goodbye", "see you", "cya", "later", "exit", "quit", "done"]
    return any(g in text.lower() for g in goodbyes)


def is_help(text: str) -> bool:
    help_words = ["help", "what can you do", "how to use", "commands", "options", "menu", "guide", "features"]
    return any(h in text.lower() for h in help_words)


def is_about(text: str) -> bool:
    about_words = ["who are you", "what are you", "your name", "about you", "introduce yourself"]
    return any(a in text.lower() for a in about_words)


# ── Intent helpers ────────────────────────────────────────────

def extract_city(text: str) -> str | None:
    patterns = [
        r"hotels?\s+in\s+([a-zA-Z\s]+?)(?:\s*$|\s+(?:for|from|with|under|between|above|sort|price|cheap|best|near))",
        r"hotels?\s+in\s+([a-zA-Z\s]+)",
        r"find\s+(?:me\s+)?hotels?\s+in\s+([a-zA-Z\s]+)",
        r"search\s+(?:for\s+)?hotels?\s+in\s+([a-zA-Z\s]+)",
        r"show\s+(?:me\s+)?hotels?\s+in\s+([a-zA-Z\s]+)",
        r"(?:i\s+)?(?:want|need|looking\s+for)\s+(?:a\s+)?hotels?\s+in\s+([a-zA-Z\s]+)",
        r"book\s+(?:a\s+)?hotels?\s+in\s+([a-zA-Z\s]+)",
        r"stay\s+in\s+([a-zA-Z\s]+)",
        r"hotels?\s+(?:near|around|at)\s+([a-zA-Z\s]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            city = m.group(1).strip().title()
            city = re.sub(r'\s+(Please|Thanks|Thank|For|From|With)$', '', city, flags=re.IGNORECASE)
            if len(city) > 1:
                return city
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

    if not OPENCAGE_KEY:
        return "❌ Error: OPENCAGE_KEY environment variable is not set on the server."

    # ── Conversational intents (check first) ──
    if is_greeting(text):
        return random.choice(GREETINGS)

    if is_goodbye(text):
        return random.choice(GOODBYE_RESPONSES)

    if is_help(text):
        return HELP_TEXT

    if is_about(text):
        return (
            "I'm **HotelBot** 🤖 — your AI-powered hotel booking assistant!\n\n"
            "I search real hotel data from **OpenStreetMap** to find nearby hotels "
            "with their contact details — phone numbers, websites, email addresses, "
            "and exact locations.\n\n"
            "This means you get **real, verified hotel data** that you can use to book directly! "
            "Just tell me a city to get started. 🏨"
        )

    if is_thanks(text):
        return random.choice(THANKS_RESPONSES)

    # ── Hotel search ──
    city = extract_city(user_input)
    if city:
        result = search_hotels(city, OPENCAGE_KEY)
        if result.get("error"):
            return f"❌ {result['error']}"
        _session["hotels"] = result["result"]
        _session["last_city"] = city
        count = len(_session['hotels'])
        return (
            f"🏙️ **Found {count} hotels in {city}!** Here are the top results:\n\n"
            + format_hotel_list(_session["hotels"])
            + f"\n\n💡 **Tip:** Say 'sort by distance', 'within 5 km', 'show more', or 'tell me more about [hotel name]' to explore!"
        )

    # ── Commands that need previous search results ──
    if not _session["hotels"]:
        if any(word in text for word in ["hotel", "book", "stay", "room", "accommodation"]):
            return (
                "I'd love to help you find a hotel! 🏨\n\n"
                "Just tell me the city. For example:\n"
                "  • **'hotels in Mumbai'**\n"
                "  • **'find hotels in Goa'**\n"
                "  • **'hotels near Jalandhar'**"
            )
        return (
            "Hey! 😊 I'm **HotelBot**, your hotel booking assistant.\n\n"
            "To get started, tell me which city you'd like to explore!\n"
            "For example: **'hotels in Mumbai'** or **'hotels in Paris'**\n\n"
            "Type **'help'** to see everything I can do! 🏨"
        )

    # Sorting
    if "sort by distance" in text or "nearest" in text or "closest" in text:
        _session["hotels"] = sort_by_distance(_session["hotels"])
        return "✅ **Sorted by distance (nearest first):**\n\n" + format_hotel_list(_session["hotels"])

    if "sort by rating" in text or "best rated" in text or "top rated" in text:
        _session["hotels"] = sort_by_rating(_session["hotels"])
        return "✅ **Sorted by rating (highest first):**\n\n" + format_hotel_list(_session["hotels"])

    if "sort by price" in text or "cheapest" in text:
        _session["hotels"] = sort_by_price(_session["hotels"])
        return "✅ **Sorted by price:**\n\n" + format_hotel_list(_session["hotels"])

    # Rating filter
    min_rating = extract_rating(text)
    if min_rating is not None:
        filtered = filter_by_rating(_session["hotels"], min_rating)
        if not filtered:
            return f"😕 No hotels with rating ≥ {min_rating}. Try a lower threshold."
        _session["hotels"] = filtered
        return f"✅ **{len(filtered)} hotel(s) rated {min_rating}+ stars:**\n\n" + format_hotel_list(filtered)

    # Distance filter
    max_km = extract_distance(text)
    if max_km is not None:
        filtered = filter_by_distance(_session["hotels"], max_km)
        _session["hotels"] = filtered
        return f"✅ **Hotels within {max_km} km of city center:**\n\n" + format_hotel_list(filtered)

    # Detail view
    if "tell me more" in text or "details" in text or "more about" in text or "info about" in text:
        m = re.search(r"(?:about|details\s+(?:of|on))\s+(.+)", user_input, re.IGNORECASE)
        if m:
            hotel = find_hotel_by_name(m.group(1).strip())
            if hotel:
                return "📋 **Hotel Details:**\n\n" + format_hotel(hotel)
            return f"😕 Couldn't find a hotel matching '{m.group(1).strip()}'. Check the name and try again."
        return "Please specify the hotel name, e.g. **'tell me more about Taj Hotel'**."

    if "show more" in text or "more results" in text or "show all" in text:
        return "📋 **More results:**\n\n" + format_hotel_list(_session["hotels"], limit=10)

    # Contact specific hotel
    if "phone" in text or "call" in text or "contact" in text or "number" in text:
        if "phone" in text or "number" in text:
            m = re.search(r"(?:phone|number|contact)\s+(?:of|for)\s+(.+)", user_input, re.IGNORECASE)
            if m:
                hotel = find_hotel_by_name(m.group(1).strip())
                if hotel:
                    phone = hotel.get("phone")
                    if phone:
                        return f"📞 **{hotel['hotel_name']}**: {phone}"
                    return f"😕 No phone number available for {hotel['hotel_name']}. Try searching for it on Google Maps."
        return "To get contact details, say **'tell me more about [hotel name]'** or search for a specific hotel."

    # New search suggestion
    if any(word in text for word in ["hotel", "book", "stay", "another", "different", "new"]):
        return (
            "Sure! Just tell me the city name. For example:\n"
            "  • **'hotels in Goa'**\n"
            "  • **'hotels in London'**"
        )

    # Catch-all
    return (
        f"🤔 I'm not sure I understand that. Here's what I can do:\n\n"
        f"🔍 Search: **'hotels in [city]'**\n"
        f"📊 Sort: **'sort by distance'** or **'sort by rating'**\n"
        f"🔎 Filter: **'within 5 km'** or **'rating above 3'**\n"
        f"📋 Details: **'tell me more about [hotel name]'**\n\n"
        f"Type **'help'** for the full guide! 😊"
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