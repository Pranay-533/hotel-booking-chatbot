import requests
from datetime import datetime, timedelta

def search_hotels(lat, lng, rapidapi_key, rapidapi_host):
    """
    Search for hotels by coordinates using Booking.com API.
    
    Args:
        lat (float): Latitude
        lng (float): Longitude
        rapidapi_key (str): RapidAPI key
        rapidapi_host (str): RapidAPI host for Booking.com
    
    Returns:
        dict: API response containing hotel results or error
    """
    try:
        url = "https://booking-com.p.rapidapi.com/v1/hotels/search-by-coordinates"
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": rapidapi_host
        }

        # Dynamically set check-in and check-out dates
        today = datetime.today().strftime("%Y-%m-%d")
        tomorrow = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")

        params = {
            "latitude": lat,
            "longitude": lng,
            "checkin_date": today,
            "checkout_date": tomorrow,
            "adults_number": 2,
            "room_number": 1,
            "order_by": "price",
            "locale": "en-gb",
            "currency": "INR",
            "filter_by_currency": "INR",
            "units": "metric"
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()  # Raise an error for bad status codes
        
        data = response.json()
        
        # Validate response structure
        if not isinstance(data, dict):
            return {"error": "Invalid response format from API", "result": []}
        
        return data
    except requests.exceptions.Timeout:
        print(f"Timeout fetching hotels for coordinates ({lat}, {lng})")
        return {"error": "Request timeout - API took too long to respond", "result": []}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching hotels: {e}")
        return {"error": f"Failed to fetch hotel details: {str(e)}", "result": []}
    except ValueError as e:
        print(f"Error parsing API response: {e}")
        return {"error": "Failed to parse API response", "result": []}
