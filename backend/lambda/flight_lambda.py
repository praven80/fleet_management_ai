"""
AWS Lambda function for flight traffic tool
Designed to work with Amazon Bedrock AgentCore Gateway
"""
import json
import urllib.request
import urllib.error
import urllib.parse
import os
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


def get_flight_traffic(airport_code: str) -> Dict[str, Any]:
    """
    Get flight traffic information for an airport to predict rental demand.
    
    Args:
        airport_code: IATA airport code (e.g., 'LAX', 'JFK', 'ORD', 'ATL')
    
    Returns:
        Dictionary with flight arrival and departure information
    """
    # Get API key from environment variable
    api_key = os.environ.get("AVIATIONSTACK_API_KEY")
    
    if not api_key or api_key == "your_aviationstack_api_key_here":
        return {
            "error": "AviationStack API key not configured. Please add AVIATIONSTACK_API_KEY to Lambda environment",
            "airport": airport_code.upper(),
            "note": "Get a free API key at https://aviationstack.com/",
            "flights": []
        }
    
    try:
        # Get flight data from AviationStack API
        params = urllib.parse.urlencode({
            "access_key": api_key,
            "arr_iata": airport_code.upper(),  # Arrivals
            "limit": 10
        })
        
        url = f"http://api.aviationstack.com/v1/flights?{params}"
        
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        if "error" in data:
            return {
                "error": f"API Error: {data['error'].get('info', 'Unknown error')}",
                "airport": airport_code.upper(),
                "flights": []
            }
        
        flights = data.get("data", [])
        
        # Format flight data
        arrivals = []
        for flight in flights:
            arrivals.append({
                "flight_number": flight.get("flight", {}).get("iata", "N/A"),
                "airline": flight.get("airline", {}).get("name", "N/A"),
                "departure_airport": flight.get("departure", {}).get("iata", "N/A"),
                "departure_city": flight.get("departure", {}).get("airport", "N/A"),
                "arrival_time": flight.get("arrival", {}).get("scheduled", "N/A"),
                "status": flight.get("flight_status", "N/A")
            })
        
        return {
            "airport": airport_code.upper(),
            "total_arrivals_shown": len(arrivals),
            "arrivals": arrivals,
            "note": "Showing recent/upcoming arrivals. High arrival count indicates increased rental demand."
        }
    
    except urllib.error.URLError as e:
        return {
            "error": f"Failed to fetch flight data: {str(e)}",
            "airport": airport_code.upper(),
            "flights": []
        }
    except Exception as e:
        return {
            "error": f"Error: {str(e)}",
            "airport": airport_code.upper(),
            "flights": []
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
        
        if tool_name == "get_flight_traffic":
            airport_code = get_named_parameter(event, "airport_code")
            
            if not airport_code:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "airport_code parameter is required"})
                }
            
            flight_data = get_flight_traffic(airport_code)
            
            return {
                "statusCode": 200,
                "body": json.dumps(flight_data)
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
