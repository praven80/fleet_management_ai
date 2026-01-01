import json
import pandas as pd
import requests
from datetime import datetime
import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal

# Simple decorator replacement for when strands is not available
def tool(func):
    """Passthrough decorator when strands is not available"""
    return func

# Helper to convert Decimal to float for JSON serialization
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
FLEET_TABLE = dynamodb.Table('hertz-fleet-inventory')


def _search_by_zip(zip_code: str, status: str = None):
    """Query DynamoDB by ZIP code using GSI"""
    try:
        if status:
            # Query with both partition and sort key
            response = FLEET_TABLE.query(
                IndexName='zip_code-index',
                KeyConditionExpression=Key('zip_code').eq(zip_code) & Key('status').eq(status)
            )
        else:
            # Query with just partition key
            response = FLEET_TABLE.query(
                IndexName='zip_code-index',
                KeyConditionExpression=Key('zip_code').eq(zip_code)
            )
        
        return response.get('Items', [])
    except Exception as e:
        print(f"Error querying DynamoDB: {e}")
        return []


def _get_summary(zip_code: str):
    vehicles = _search_by_zip(zip_code)
    if not vehicles:
        return {"error": f"No vehicles found for {zip_code}"}

    df = pd.DataFrame(vehicles)
    return {
        "zip_code": zip_code,
        "location": vehicles[0]["location"],
        "total_vehicles": len(vehicles),
        "available": len(df[df["status"] == "available"]),
        "rented": len(df[df["status"] == "rented"]),
        "maintenance": len(df[df["status"] == "maintenance"]),
        "categories": df["category"].value_counts().to_dict(),
        "avg_daily_rate": round(df["daily_rate"].mean(), 2),
    }


def _search_vehicles(make: str = None, model: str = None, category: str = None, status: str = None):
    """Search vehicles across all locations by make, model, category, or status"""
    try:
        # Build filter expression
        filter_expressions = []
        
        if make:
            filter_expressions.append(Attr('make').contains(make.title()))
        if model:
            filter_expressions.append(Attr('model').contains(model.title()))
        if category:
            filter_expressions.append(Attr('category').eq(category.lower()))
        if status:
            filter_expressions.append(Attr('status').eq(status))
        
        # Scan with filters (for cross-location search)
        if filter_expressions:
            filter_expr = filter_expressions[0]
            for expr in filter_expressions[1:]:
                filter_expr = filter_expr & expr
            
            response = FLEET_TABLE.scan(FilterExpression=filter_expr, Limit=100)
        else:
            response = FLEET_TABLE.scan(Limit=100)
        
        return response.get('Items', [])
    except Exception as e:
        print(f"Error scanning DynamoDB: {e}")
        return []


@tool
def search_fleet_by_zip(zip_code: str, status: str = None) -> str:
    """
    Search Hertz fleet by specific ZIP code location.
    
    ONLY use this tool when user explicitly provides a ZIP code number.

    Args:
        zip_code: ZIP code (e.g., '90001', '10001')
        status: Optional status filter ('available', 'rented', 'maintenance')

    Returns:
        JSON with vehicles list for that specific ZIP code
    """
    vehicles = _search_by_zip(zip_code, status)

    if not vehicles:
        return json.dumps({"message": f"No vehicles found for {zip_code}", "vehicles": []})

    return json.dumps(
        {
            "zip_code": zip_code,
            "location": vehicles[0]["location"],
            "count": len(vehicles),
            "vehicles": vehicles,
        },
        default=decimal_default
    )


@tool
def search_vehicles_general(make: str = None, model: str = None, category: str = None, status: str = None) -> str:
    """
    Search Hertz fleet across ALL locations nationwide by vehicle make, model, or category.
    
    USE THIS TOOL when user asks:
    - "Do you have [car name]?" 
    - "Where can I find [car]?"
    - "Show me [type of car]"
    - Any question about vehicles WITHOUT a specific ZIP code
    
    DO NOT use search_fleet_by_zip unless user explicitly provides a ZIP code.

    Args:
        make: Vehicle make/brand (e.g., 'Toyota', 'Honda', 'Ford')
        model: Vehicle model (e.g., 'Camry', 'CR-V', 'Mustang')
        category: Vehicle category (e.g., 'Sedan', 'SUV', 'Sports', 'Electric')
        status: Optional status filter ('available', 'rented', 'maintenance')

    Returns:
        JSON with matching vehicles across all locations
    """
    vehicles = _search_vehicles(make, model, category, status)

    if not vehicles:
        search_terms = []
        if make:
            search_terms.append(f"make: {make}")
        if model:
            search_terms.append(f"model: {model}")
        if category:
            search_terms.append(f"category: {category}")
        if status:
            search_terms.append(f"status: {status}")
        
        return json.dumps({
            "message": f"No vehicles found matching {', '.join(search_terms)}",
            "vehicles": []
        })

    # Group by location for better presentation
    locations = {}
    for v in vehicles:
        loc = v["location"]
        if loc not in locations:
            locations[loc] = []
        locations[loc].append(v)

    return json.dumps(
        {
            "count": len(vehicles),
            "locations_found": len(locations),
            "vehicles": vehicles,
            "by_location": locations,
        },
        default=decimal_default
    )


@tool
def get_fleet_summary(zip_code: str) -> str:
    """
    Get fleet summary for a ZIP code.

    Args:
        zip_code: ZIP code (e.g., '90001')

    Returns:
        JSON with fleet statistics
    """
    return json.dumps(_get_summary(zip_code), default=decimal_default)


@tool
def get_national_holidays(year: int = None, month: int = None) -> str:
    """
    Get U.S. national holidays for demand prediction analysis.
    Use this to predict high-demand periods for car rentals.
    
    Holidays typically mean increased travel and higher rental demand.

    Args:
        year: Year to get holidays for (e.g., 2024, 2025). Defaults to current year.
        month: Optional month number (1-12) to filter holidays for a specific month.

    Returns:
        JSON with list of U.S. national holidays including dates and names
    """
    try:
        # Use current year if not specified
        if year is None:
            year = datetime.now().year
        
        # Call Nager.Date API for US holidays
        url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/US"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        holidays = response.json()
        
        # Filter by month if specified
        if month is not None:
            holidays = [h for h in holidays if datetime.fromisoformat(h['date']).month == month]
        
        # Format for better readability
        formatted_holidays = []
        for holiday in holidays:
            formatted_holidays.append({
                "date": holiday['date'],
                "name": holiday['name'],
                "localName": holiday.get('localName', holiday['name']),
                "countryCode": holiday['countryCode'],
                "global": holiday.get('global', False),
                "types": holiday.get('types', [])
            })
        
        return json.dumps({
            "year": year,
            "month": month if month else "all",
            "count": len(formatted_holidays),
            "holidays": formatted_holidays
        }, indent=2)
    
    except requests.RequestException as e:
        return json.dumps({
            "error": f"Failed to fetch holidays: {str(e)}",
            "holidays": []
        })
    except Exception as e:
        return json.dumps({
            "error": f"Error: {str(e)}",
            "holidays": []
        })


@tool
def get_local_events(zip_code: str, start_date: str = None, end_date: str = None, size: int = 20) -> str:
    """
    Get upcoming local events and concerts by ZIP code using Ticketmaster API.
    Use this to predict rental demand - major events mean increased travel and car rental needs.
    
    Events like concerts, sports games, festivals drive significant rental demand in the area.

    Args:
        zip_code: ZIP code to search for events (e.g., '90001', '10001')
        start_date: Optional start date in YYYY-MM-DD format. Defaults to today.
        end_date: Optional end date in YYYY-MM-DD format. Defaults to 30 days from start.
        size: Number of events to return (default 20, max 200)

    Returns:
        JSON with list of upcoming events including name, date, venue, and type
    """
    try:
        import os
        
        # Get API key from environment
        api_key = os.getenv("TICKETMASTER_API_KEY")
        if not api_key:
            return json.dumps({
                "error": "Ticketmaster API key not configured. Set TICKETMASTER_API_KEY environment variable.",
                "events": []
            })
        
        # Set default dates if not provided
        if start_date is None:
            start_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            start_date = f"{start_date}T00:00:00Z"
        
        if end_date is None:
            # Default to 30 days from start
            end_dt = datetime.now() + pd.Timedelta(days=30)
            end_date = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            end_date = f"{end_date}T23:59:59Z"
        
        # Call Ticketmaster Discovery API
        url = "https://app.ticketmaster.com/discovery/v2/events.json"
        params = {
            "apikey": api_key,
            "postalCode": zip_code,
            "countryCode": "US",
            "startDateTime": start_date,
            "endDateTime": end_date,
            "size": min(size, 200),  # Cap at 200
            "sort": "date,asc"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Check if events exist
        if "_embedded" not in data or "events" not in data["_embedded"]:
            return json.dumps({
                "zip_code": zip_code,
                "count": 0,
                "events": [],
                "message": f"No events found for ZIP code {zip_code}"
            })
        
        events = data["_embedded"]["events"]
        
        # Format events for better readability
        formatted_events = []
        for event in events:
            # Extract venue info
            venue_info = {}
            if "_embedded" in event and "venues" in event["_embedded"]:
                venue = event["_embedded"]["venues"][0]
                venue_info = {
                    "name": venue.get("name", "Unknown"),
                    "city": venue.get("city", {}).get("name", "Unknown"),
                    "state": venue.get("state", {}).get("stateCode", "Unknown"),
                    "address": venue.get("address", {}).get("line1", "Unknown")
                }
            
            # Extract date info
            dates = event.get("dates", {})
            start_info = dates.get("start", {})
            event_date = start_info.get("localDate", "Unknown")
            event_time = start_info.get("localTime", "TBD")
            
            # Extract classifications
            classifications = event.get("classifications", [{}])[0]
            segment = classifications.get("segment", {}).get("name", "Unknown")
            genre = classifications.get("genre", {}).get("name", "Unknown")
            
            formatted_events.append({
                "name": event.get("name", "Unknown"),
                "date": event_date,
                "time": event_time,
                "type": segment,
                "genre": genre,
                "venue": venue_info,
                "url": event.get("url", ""),
                "priceRanges": event.get("priceRanges", [])
            })
        
        return json.dumps({
            "zip_code": zip_code,
            "count": len(formatted_events),
            "events": formatted_events,
            "page": data.get("page", {})
        }, indent=2)
    
    except requests.RequestException as e:
        return json.dumps({
            "error": f"Failed to fetch events: {str(e)}",
            "events": []
        })
    except Exception as e:
        return json.dumps({
            "error": f"Error: {str(e)}",
            "events": []
        })


# Export helper functions for direct use in app.py
def search_by_zip(zip_code: str, status: str = None):
    return _search_by_zip(zip_code, status)


def get_summary(zip_code: str):
    return _get_summary(zip_code)
