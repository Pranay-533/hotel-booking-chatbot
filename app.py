from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import re
from src.coordinates import get_coordinates
from src.hotel_search import search_hotels
from src.utils import apply_filters, get_hotel_details, format_hotel_response

# Initialize Flask app
app = Flask(__name__)
load_dotenv()

# Load API keys from environment variables
rapidapi_key = os.getenv("RAPIDAPI_KEY")
rapidapi_host = os.getenv("RAPIDAPI_HOST")
opencage_key = os.getenv("OPENCAGE_KEY")

# Validate that all required API keys are set
if not all([rapidapi_key, rapidapi_host, opencage_key]):
    print("⚠️  WARNING: Missing required environment variables!")
    print("   OPENCAGE_KEY:", "✓" if opencage_key else "✗ Missing")
    print("   RAPIDAPI_KEY:", "✓" if rapidapi_key else "✗ Missing")
    print("   RAPIDAPI_HOST:", "✓" if rapidapi_host else "✗ Missing")
    print("   Please set these in your .env file")

# Global context to maintain state between requests
last_city = None
last_hotels = []

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    global last_city, last_hotels
    data = request.get_json(silent=True)  # returns None instead of raising on bad Content-Type
    if not data:
        return jsonify({"reply": "Invalid request. Please send a JSON body with a 'message' field."}), 400
    user_input = data.get("message", "").strip().lower()

    # Main logic - search for hotels in a city
    city_match = re.search(r"(?:hotel|hotels) in ([a-zA-Z ]+)", user_input)
    if city_match:
        city = city_match.group(1).strip()
        if not city:
            return jsonify({"reply": "Please specify a city name. For example: 'hotels in Mumbai'."})
        lat, lng = get_coordinates(city, opencage_key)

        if lat and lng:
            result = search_hotels(lat, lng, rapidapi_key, rapidapi_host)
            
            # Check for errors in the result
            if result.get("error"):
                return jsonify({"reply": f"❌ Error: {result['error']}"})
            
            hotels = result.get("result", [])
            last_city = city
            last_hotels = hotels
            if not hotels:
                return jsonify({"reply": f"Sorry, no hotels found in {city}."})
            hotels = apply_filters(user_input, hotels)
            return jsonify({"reply": format_hotel_response(city, hotels)})
        else:
            return jsonify({"reply": f"❌ Couldn't find coordinates for {city}. Please check the city name."})

    # Apply filters to previous search results
    if last_city and last_hotels and any(x in user_input for x in ["sort by", "within", "price between"]):
        filtered = apply_filters(user_input, last_hotels)
        return jsonify({"reply": format_hotel_response(last_city, filtered)})

    # Get details about a specific hotel
    if last_hotels:
        details = get_hotel_details(user_input, last_hotels)
        if details:
            return jsonify({"reply": details})

    # Handle greetings
    if any(greet in user_input for greet in ["hi", "hello", "hey"]):
        return jsonify({"reply": "Hello! 👋 How may I help you with hotel booking today?"})

    # Default response for unrecognized input
    return jsonify({"reply": "I'm sorry, I didn't understand that. Try asking for hotels in a city like 'show me hotels in Mumbai'."})

if __name__ == "__main__":
    app.run(debug=True)
