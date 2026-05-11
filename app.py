"""
app.py  –  Flask API backend for the Hotel Booking Chatbot.

Deployed on Render. Serves JSON API only (no HTML templates).
Frontend is deployed separately on Vercel.
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
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "booking-com15.p.rapidapi.com")

# ── Per-session state (in-memory; resets on server restart) ────
_session = {
    "hotels": [],
    "last_city": None,
}


# ── Conversational responses ──────────────────────────────────

GREETINGS = [
    "Hello! 👋 I'm HotelBot, your personal hotel booking assistant! I can help you find the perfect hotel anywhere in the world. Just tell me a city, like **'hotels in Mumbai'** or **'find hotels in Paris'** and I'll get right on it! 🏨",
    "Hey there! 😊 Welcome to HotelBot! I'm here to help you discover amazing hotels. Try saying something like **'hotels in Delhi'** or **'show me hotels in Goa'** to get started!",
    "Hi! 🙌 Great to meet you! I'm your AI hotel assistant. Tell me which city you'd like to explore and I'll find the best hotels for you. For example: **'hotels in Bangalore'** ✨",
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
    "  • 'show me hotels in Delhi'\n\n"
    "📊 **Sort Results:**\n"
    "  • 'sort by price' or 'cheapest'\n"
    "  • 'sort by rating' or 'best rated'\n\n"
    "🔎 **Filter Results:**\n"
    "  • 'price under 3000'\n"
    "  • 'price between 1000 and 5000'\n"
    "  • 'rating above 8'\n"
    "  • 'within 5 km'\n\n"
    "📋 **Hotel Details:**\n"
    "  • 'tell me more about [hotel name]'\n"
    "  • 'show more results'\n\n"
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
    thanks = ["thank", "thanks", "thx", "ty", "appreciate", "grateful", "awesome", "great", "nice", "cool", "perfect"]
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
    # Multiple patterns for natural language
    patterns = [
        r"hotels?\s+in\s+([a-zA-Z\s]+?)(?:\s*$|\s+(?:for|from|with|under|between|above|sort|price|cheap|best))",
        r"hotels?\s+in\s+([a-zA-Z\s]+)",
        r"find\s+(?:me\s+)?hotels?\s+in\s+([a-zA-Z\s]+)",
        r"search\s+(?:for\s+)?hotels?\s+in\s+([a-zA-Z\s]+)",
        r"show\s+(?:me\s+)?hotels?\s+in\s+([a-zA-Z\s]+)",
        r"(?:i\s+)?(?:want|need|looking\s+for)\s+(?:a\s+)?hotels?\s+in\s+([a-zA-Z\s]+)",
        r"book\s+(?:a\s+)?hotels?\s+in\s+([a-zA-Z\s]+)",
        r"stay\s+in\s+([a-zA-Z\s]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            city = m.group(1).strip().title()
            # Clean up trailing common words
            city = re.sub(r'\s+(Please|Thanks|Thank|For|From|With)$', '', city, flags=re.IGNORECASE)
            if len(city) > 1:
                return city
    return None


def extract_price_range(text: str) -> tuple[float, float] | None:
    m = re.search(r"between\s+(\d+)\s+and\s+(\d+)", text, re.IGNORECASE)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"under\s+(\d+)", text, re.IGNORECASE)
    if m:
        return 0.0, float(m.group(1))
    m = re.search(r"(?:below|less\s+than|cheaper\s+than|max)\s+(\d+)", text, re.IGNORECASE)
    if m:
        return 0.0, float(m.group(1))
    m = re.search(r"above\s+(\d+)", text, re.IGNORECASE)
    if m:
        return float(m.group(1)), float("inf")
    m = re.search(r"(?:over|more\s+than|min(?:imum)?)\s+(\d+)", text, re.IGNORECASE)
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
        return "❌ Error: API Key missing! The RAPIDAPI_KEY environment variable is not set on the server."

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
            "I can search for hotels in any city worldwide, filter by price and rating, "
            "sort results, and give you detailed information about any hotel.\n\n"
            "I'm powered by the Booking.com API and I'm here to make your hotel search "
            "quick and easy! Just tell me a city to get started. 🏨"
        )
    
    if is_thanks(text):
        return random.choice(THANKS_RESPONSES)

    # ── Hotel search ──
    city = extract_city(user_input)
    if city:
        result = search_hotels(city, RAPIDAPI_KEY, RAPIDAPI_HOST)
        if result.get("error"):
            return f"❌ {result['error']}"
        _session["hotels"] = result["result"]
        _session["last_city"] = city
        count = len(_session['hotels'])
        return (
            f"🏙️ **Found {count} hotels in {city}!** Here are the top results:\n\n"
            + format_hotel_list(_session["hotels"])
            + f"\n\n💡 **Tip:** You can say 'sort by price', 'rating above 8', or 'tell me more about [hotel name]' to explore further!"
        )

    # ── Commands that need previous search results ──
    if not _session["hotels"]:
        # Smart fallback - try to understand what the user wants
        if any(word in text for word in ["hotel", "book", "stay", "room", "accommodation"]):
            return (
                "I'd love to help you find a hotel! 🏨\n\n"
                "Just tell me the city you're interested in. For example:\n"
                "  • **'hotels in Mumbai'**\n"
                "  • **'find hotels in Goa'**\n"
                "  • **'show me hotels in Delhi'**"
            )
        return (
            "Hey! 😊 I'm HotelBot, your hotel booking assistant.\n\n"
            "To get started, just tell me which city you'd like to explore!\n"
            "For example: **'hotels in Mumbai'** or **'hotels in Paris'**\n\n"
            "Type **'help'** to see everything I can do! 🏨"
        )

    # Sorting
    if "sort by price" in text or "cheapest" in text or "cheap" in text or "lowest price" in text:
        _session["hotels"] = sort_by_price(_session["hotels"])
        return "✅ **Sorted by price (lowest first):**\n\n" + format_hotel_list(_session["hotels"])

    if "sort by rating" in text or "best rated" in text or "top rated" in text or "highest rated" in text:
        _session["hotels"] = sort_by_rating(_session["hotels"])
        return "✅ **Sorted by rating (highest first):**\n\n" + format_hotel_list(_session["hotels"])

    # Price filter
    price_range = extract_price_range(text)
    if price_range:
        lo, hi = price_range
        filtered = filter_by_price(_session["hotels"], lo, hi)
        if not filtered:
            return f"😕 No hotels found in that price range. Try a wider range or say **'show all'** to see all results."
        _session["hotels"] = filtered
        return f"✅ **{len(filtered)} hotel(s) match your budget:**\n\n" + format_hotel_list(filtered)

    # Rating filter
    min_rating = extract_rating(text)
    if min_rating is not None:
        filtered = filter_by_rating(_session["hotels"], min_rating)
        if not filtered:
            return f"😕 No hotels with rating ≥ {min_rating}. Try a lower threshold."
        _session["hotels"] = filtered
        return f"✅ **{len(filtered)} hotel(s) rated {min_rating}+:**\n\n" + format_hotel_list(filtered)

    # Distance filter
    max_km = extract_distance(text)
    if max_km is not None:
        filtered = filter_by_distance(_session["hotels"], max_km)
        _session["hotels"] = filtered
        return f"✅ **Hotels within {max_km} km:**\n\n" + format_hotel_list(filtered)

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
        return "📋 **All results:**\n\n" + format_hotel_list(_session["hotels"], limit=10)

    # New search suggestion
    if any(word in text for word in ["hotel", "book", "stay", "room", "another", "different", "new"]):
        return (
            "Sure! Just tell me the city name. For example:\n"
            "  • **'hotels in Goa'**\n"
            "  • **'hotels in London'**"
        )

    # Catch-all with personality
    return (
        f"🤔 I'm not sure I understand that. Here's what I can do:\n\n"
        f"🔍 Search: **'hotels in [city]'**\n"
        f"📊 Sort: **'sort by price'** or **'sort by rating'**\n"
        f"💰 Filter: **'price under 3000'** or **'rating above 8'**\n"
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