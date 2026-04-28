import requests

def get_coordinates(city, api_key):
    """
    Convert city name to coordinates using OpenCage Geocoding API.
    
    Args:
        city (str): City name
        api_key (str): OpenCage API key
    
    Returns:
        tuple: (latitude, longitude) or (None, None) if not found
    """
    try:
        url = "https://api.opencagedata.com/geocode/v1/json"
        params = {"q": city, "key": api_key}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Raise an error for bad status codes
        
        data = response.json()
        
        if data.get('results'):
            lat = data['results'][0]['geometry']['lat']
            lng = data['results'][0]['geometry']['lng']
            return lat, lng
        return None, None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching coordinates for {city}: {e}")
        return None, None
    except (KeyError, ValueError) as e:
        print(f"Error parsing OpenCage API response: {e}")
        return None, None
