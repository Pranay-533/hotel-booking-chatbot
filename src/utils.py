# src/utils.py - Shared utility functions for the chatbot

import re

def apply_filters(user_input, hotels):
    """
    Apply various filters to hotel results based on user input.
    
    Supports:
    - "sort by price" - Sort by price ascending
    - "sort by rating" - Sort by rating descending
    - "within X km" - Filter by distance
    - "price between X and Y" - Filter by price range
    
    Args:
        user_input (str): User's filter request
        hotels (list): List of hotel dictionaries
    
    Returns:
        list: Filtered hotel list
    """
    if "sort by price" in user_input:
        def _price_key(h):
            p = h.get("min_total_price")
            try:
                return float(p) if p is not None else float('inf')
            except (ValueError, TypeError):
                return float('inf')
        hotels = sorted(hotels, key=_price_key)
    elif "sort by rating" in user_input:
        hotels = sorted(hotels, key=lambda x: x.get("review_score") or 0, reverse=True)
    elif "within" in user_input:
        distance_match = re.search(r"within ([\d.]+) ?km", user_input)
        if distance_match:
            max_distance = float(distance_match.group(1))
            def safe_distance(h):
                d = h.get("distance")
                try:
                    return float(d) if d is not None else float('inf')
                except (ValueError, TypeError):
                    return float('inf')
            hotels = [h for h in hotels if safe_distance(h) <= max_distance]
    elif "price between" in user_input:
        price_match = re.search(r"price between ([\d.]+) and ([\d.]+)", user_input)
        if price_match:
            min_price = float(price_match.group(1))
            max_price = float(price_match.group(2))
            def safe_price(h):
                p = h.get("min_total_price")
                try:
                    return float(p) if p is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0
            hotels = [h for h in hotels if min_price <= safe_price(h) <= max_price]
    return hotels


def get_hotel_details(user_input, hotels):
    """
    Extract and return detailed information about a specific hotel.
    
    User can ask: "tell me more about [hotel name]"
    
    Args:
        user_input (str): User's request
        hotels (list): List of hotel dictionaries
    
    Returns:
        str: Formatted hotel details or None if not found
    """
    match = re.search(r"(?:tell me more about|more details about|more about) (.+)", user_input)
    if match:
        name_query = match.group(1).strip().lower()
        for hotel in hotels:
            if name_query in hotel.get("hotel_name", "").lower():
                details = f"🏨 {hotel.get('hotel_name', 'N/A')}\n"
                details += f"⭐ Rating: {hotel.get('review_score', 'N/A')}\n"
                price = hotel.get("min_total_price", 'N/A')
                if isinstance(price, (float, int)):
                    price = f"{price:.2f}"
                details += f"💸 Price: {price} {hotel.get('currencycode', '')}\n"
                details += f"🏷️ Type: {hotel.get('accommodation_type_name', 'N/A')}\n"
                details += f"📍 Address: {hotel.get('address', 'N/A')}\n"
                details += f"📏 Distance: {hotel.get('distance', 'N/A')} km\n"
                return details
    return None


def format_hotel_response(city, hotels):
    """
    Format hotel search results into a readable response.
    
    Args:
        city (str): City name
        hotels (list): List of hotel dictionaries
    
    Returns:
        str: Formatted hotel list response
    """
    if not hotels:
        return f"Sorry, no hotels were found in {city.title()} matching your criteria. Try broadening your filters."
    top_hotels = hotels[:5]
    response = f"Here are the top {len(top_hotels)} hotel(s) in {city.title()}:\n"
    for hotel in top_hotels:
        name = hotel.get("hotel_name", "N/A")
        rating = hotel.get("review_score", "N/A")
        price = hotel.get("min_total_price", "N/A")
        currency = hotel.get("currencycode", "")
        if isinstance(price, (float, int)):
            price = f"{price:.2f}"
        response += f"\n🏨 {name}\n⭐ Rating: {rating}\n💸 Price: {price} {currency}\n"
    response += "\nWould you like to apply more filters? (e.g., sort by rating, within 5 km, price between 1000 and 2000)"
    return response
