"""
AWS Lambda function for weather forecast tool
Designed to work with Amazon Bedrock AgentCore Gateway
"""
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any


def get_tool_name(context) -> str:
    """Extract tool name from Lambda context (AgentCore Gateway passes it here)"""
    try:
        # AgentCore Gateway passes the tool name in the context
        extended_tool_name = context.client_context.custom.get("bedrockAgentCoreToolName", "")
        # The tool name format is "TargetName___tool_name"
        if "___" in extended_tool_name:
            return extended_tool_name.split("___")[1]
        return extended_tool_name
    except (AttributeError, KeyError):
        return ""


def get_named_parameter(event: Dict[str, Any], name: str) -> Any:
    """Extract named parameter from Lambda event"""
    # AgentCore Gateway passes parameters directly in the event
    return event.get(name)


def get_weather_forecast(location: str, days: int = 7) -> Dict[str, Any]:
    """
    Get weather forecast for a location to help with demand prediction.
    
    Args:
        location: City name or location (e.g., 'Los Angeles', 'New York')
        days: Number of days to forecast (default: 7, max: 16)
    
    Returns:
        Dictionary with weather forecast data
    """
    try:
        # Use Open-Meteo Geocoding API to get coordinates
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(location)}&count=1&language=en&format=json"
        with urllib.request.urlopen(geocode_url, timeout=5) as response:
            geo_data = json.loads(response.read().decode())
        
        if not geo_data.get("results"):
            return {
                "error": f"Location '{location}' not found",
                "forecast": []
            }
        
        result = geo_data["results"][0]
        lat = result["latitude"]
        lon = result["longitude"]
        location_name = result["name"]
        
        # Get weather forecast from Open-Meteo
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weathercode&temperature_unit=fahrenheit&timezone=auto&forecast_days={min(days, 16)}"
        with urllib.request.urlopen(weather_url, timeout=5) as response:
            weather_data = json.loads(response.read().decode())
        
        # Format forecast
        daily = weather_data["daily"]
        forecast = []
        for i in range(len(daily["time"])):
            forecast.append({
                "date": daily["time"][i],
                "temp_max_f": daily["temperature_2m_max"][i],
                "temp_min_f": daily["temperature_2m_min"][i],
                "precipitation_mm": daily["precipitation_sum"][i],
                "precipitation_probability": daily["precipitation_probability_max"][i],
                "weather_code": daily["weathercode"][i]
            })
        
        return {
            "location": location_name,
            "latitude": lat,
            "longitude": lon,
            "forecast_days": len(forecast),
            "forecast": forecast
        }
    
    except urllib.error.URLError as e:
        return {
            "error": f"Failed to fetch weather: {str(e)}",
            "forecast": []
        }
    except Exception as e:
        return {
            "error": f"Error: {str(e)}",
            "forecast": []
        }


def lambda_handler(event, context):
    """
    AWS Lambda handler for AgentCore Gateway
    
    The tool name is extracted from the event, and parameters are passed
    in the event's parameters field.
    """
    try:
        # Debug: log the event and context
        print(f"Received event: {json.dumps(event)}")
        print(f"Context client_context: {context.client_context if hasattr(context, 'client_context') else 'None'}")
        
        tool_name = get_tool_name(context)
        print(f"Extracted tool name: {tool_name}")
        
        if tool_name == "get_weather_forecast":
            location = get_named_parameter(event, "location")
            days = get_named_parameter(event, "days")
            
            if not location:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "location parameter is required"})
                }
            
            # Default days to 7 if not provided
            if days is None:
                days = 7
            
            weather_data = get_weather_forecast(location, int(days))
            
            return {
                "statusCode": 200,
                "body": json.dumps(weather_data)
            }
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Unknown tool: {tool_name}"})
            }
    
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Internal error: {str(e)}"})
        }
