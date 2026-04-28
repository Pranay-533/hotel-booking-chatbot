import re
import os
from dotenv import load_dotenv
from src.coordinates import get_coordinates
from src.hotel_search import search_hotels
from src.utils import apply_filters, get_hotel_details, format_hotel_response

# Load environment variables
load_dotenv()

rapidapi_key = os.getenv("RAPIDAPI_KEY")
rapidapi_host = os.getenv("RAPIDAPI_HOST")
opencage_key = os.getenv("OPENCAGE_KEY")

# Maintain context
last_city = None
last_hotels = []

def respond_to_user_input(user_input):
    global last_city, last_hotels
    user_input = user_input.lower()

    # Detect hotel query and extract city first — matches both "hotel in" and "hotels in"
    city_match = re.search(r"(?:hotel|hotels) in ([a-zA-Z ]+)", user_input)
    if city_match:
        city = city_match.group(1).strip()
        if not city:
            return "Please specify a city name. For example: 'hotels in Mumbai'."
        lat, lng = get_coordinates(city, opencage_key)
        if lat and lng:
            result = search_hotels(lat, lng, rapidapi_key, rapidapi_host)
            # Check for API errors before proceeding
            if result.get("error"):
                return f"❌ Error: {result['error']}"
            hotels = result.get("result", [])
            last_city = city
            last_hotels = hotels
            if not hotels:
                return f"Sorry, I couldn't find any hotels in {city}."

            hotels = apply_filters(user_input, hotels)
            return format_hotel_response(city, hotels)
        else:
            return f"❌ Sorry, I couldn't find the coordinates for {city}."

    # Apply filters to previous result
    if last_city and last_hotels and any(x in user_input for x in ["sort by", "within", "price between"]):
        filtered = apply_filters(user_input, last_hotels)
        return format_hotel_response(last_city, filtered)

    # Check for detailed hotel query
    if last_hotels:
        details = get_hotel_details(user_input, last_hotels)
        if details:
            return details

    # Greetings after hotel query
    if any(greet in user_input for greet in ["hi", "hello", "hey"]):
        return "Hello! How may I help you with hotel booking today?"

    return "I'm sorry, I didn't understand that. You can ask me to show hotels in a city."

# Example interaction loop
if __name__ == "__main__":
    print("Welcome to HotelBot! Type your query or 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        response = respond_to_user_input(user_input)
        print(f"Bot: {response}")
