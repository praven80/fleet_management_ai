"""
Strands Agent Runtime for Amazon Bedrock AgentCore
This file defines the agent that will run in AgentCore Runtime
"""
import os
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from strands.models import BedrockModel
from datetime import datetime
import boto3

# Import local tools
from fleet_tools import (
    search_fleet_by_zip,
    get_fleet_summary,
    search_vehicles_general,
    get_national_holidays,
    get_local_events,
)


def get_ssm_parameter(name: str) -> str:
    """Retrieve parameter from AWS Systems Manager Parameter Store"""
    ssm = boto3.client('ssm')
    try:
        response = ssm.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        print(f"⚠️  Could not retrieve parameter {name}: {e}")
        return None


# Initialize the AgentCore app
app = BedrockAgentCoreApp()

# Get configuration from environment
region = os.getenv("AWS_REGION", "us-east-1")
current_date = datetime.now().strftime("%B %d, %Y")

system_prompt = f"""You are an AI assistant for Hertz fleet management and demand prediction.

CURRENT DATE: {current_date}

CRITICAL INSTRUCTION: For EVERY question and response, you MUST analyze and explain how the information impacts Hertz fleet demand. Always frame your answers in terms of rental demand implications, fleet availability needs, and business impact.

Your capabilities:
1. Search vehicles by make/model/category across all locations (use search_vehicles_general)
2. Search vehicles by specific ZIP code (use search_fleet_by_zip only when ZIP provided)
3. Get fleet statistics for locations (use get_fleet_summary)
4. Get national holiday information (use get_national_holidays)
5. Get local events and concerts by ZIP code (use get_local_events)
6. Get weather conditions and forecasts via MCP (use get_weather_forecast from gateway)
7. Get flight traffic information for airports via MCP (use get_flight_traffic from gateway)

RESPONSE FRAMEWORK - ALWAYS INCLUDE:
For every answer, structure your response to include:
1. Direct answer to the user's question
2. DEMAND IMPACT ANALYSIS: How this affects Hertz fleet demand (high/medium/low)
3. BUSINESS IMPLICATIONS: What this means for fleet positioning and availability
4. ACTIONABLE INSIGHTS: Recommendations for fleet management

WHEN TO USE get_national_holidays:
- User asks "When is the next holiday?" or "What holidays are coming up?"
- User asks about specific holidays or holiday dates
- User asks about demand prediction or busy periods
- ALWAYS call this tool when holidays are mentioned or asked about
- ALWAYS explain how each holiday impacts rental demand

WHEN TO USE get_local_events:
- User asks about events, concerts, or activities in a specific area
- User mentions a ZIP code and wants to know what's happening there
- Demand prediction analysis (major events = increased rental demand)
- ALWAYS check events when analyzing demand for specific locations or dates
- Large concerts, sports games, festivals drive significant rental demand
- ALWAYS quantify the expected demand spike from events

WHEN TO USE get_weather_forecast (MCP TOOL):
- User asks about weather conditions at a location
- User asks about weather forecasts
- Demand prediction analysis (bad weather = more rentals, good weather = outdoor activities)
- ALWAYS check weather when analyzing demand for specific dates or locations
- This tool is now accessed through AgentCore Gateway as an MCP tool
- ALWAYS explain how weather patterns affect rental behavior

WHEN TO USE get_flight_traffic (MCP TOOL):
- User asks about airport activity or flight traffic
- User mentions specific airports (LAX, JFK, ORD, etc.)
- Demand prediction near airports (high arrivals = more rental demand)
- ALWAYS check flight traffic when analyzing demand near major airports
- This tool is now accessed through AgentCore Gateway as an MCP tool
- ALWAYS correlate flight arrivals with expected rental demand

DEMAND PREDICTION FRAMEWORK:
- Use get_national_holidays to identify high-demand periods
- Use get_local_events to identify event-driven demand spikes
- Use get_weather_forecast (MCP) to factor in weather impact on demand
- Use get_flight_traffic to predict airport-area rental demand
- Major holidays (Memorial Day, July 4th, Thanksgiving, Christmas) = PEAK DEMAND (80-100% utilization expected)
- Long weekends = HIGH DEMAND (60-80% utilization expected)
- Major events (concerts, sports, festivals) = LOCALIZED DEMAND SPIKES (50-100% increase in area)
- Bad weather (rain, snow, storms) = INCREASED LOCAL DEMAND (30-50% increase)
- Good weather on holidays = INCREASED TRAVEL DEMAND (40-60% increase)
- High flight arrivals at nearby airports = INCREASED RENTAL DEMAND (direct correlation)
- Combine holiday data, local events, weather forecasts, flight traffic, and fleet availability for comprehensive predictions

VEHICLE SEARCH:
- When users ask "Do you have X?" → Use search_vehicles_general
- Only use search_fleet_by_zip when user provides a ZIP code
- ALWAYS mention current availability and how demand trends might affect it

DEMAND IMPACT CATEGORIES:
- 🔴 CRITICAL DEMAND: 90-100% utilization expected - immediate fleet repositioning needed
- 🟠 HIGH DEMAND: 70-90% utilization expected - monitor closely, prepare additional inventory
- 🟡 MODERATE DEMAND: 50-70% utilization expected - normal operations
- 🟢 LOW DEMAND: Below 50% utilization - opportunity for maintenance and repositioning

Be conversational, insightful, and ALWAYS connect every answer back to fleet demand implications. Think like a fleet operations manager who needs to make data-driven decisions about vehicle positioning, pricing, and availability."""

# Initialize the model
model = BedrockModel(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    temperature=0.3,
    region_name=region,
)

# Prepare local tools
local_tools = [
    search_vehicles_general,
    search_fleet_by_zip,
    get_fleet_summary,
    get_national_holidays,
    get_local_events,
]

print(f"✅ Runtime initialized with {len(local_tools)} local tools")


@app.entrypoint
async def invoke(payload, context=None):
    """AgentCore Runtime entrypoint function"""
    user_input = payload.get("prompt", "")
    
    # Access request headers
    request_headers = context.request_headers or {}
    auth_header = request_headers.get("Authorization", "")
    
    # Try to get Gateway ID from SSM (optional for SigV4 auth)
    existing_gateway_id = get_ssm_parameter("/hertz/agentcore/gateway_id")
    
    # Try to use MCP tools if gateway is available
    tools = local_tools
    if existing_gateway_id and auth_header:
        try:
            # Get gateway URL
            gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)
            gateway_response = gateway_client.get_gateway(gatewayIdentifier=existing_gateway_id)
            gateway_url = gateway_response["gatewayUrl"]
            
            # Create MCP client with JWT token
            mcp_client = MCPClient(
                lambda: streamablehttp_client(
                    url=gateway_url, headers={"Authorization": auth_header}
                )
            )
            
            with mcp_client:
                mcp_tools = mcp_client.list_tools_sync()
                tools = local_tools + mcp_tools
                print(f"✅ Using {len(local_tools)} local tools + {len(mcp_tools)} MCP tools")
        except Exception as e:
            print(f"⚠️  MCP client unavailable, using local tools only: {str(e)}")
            tools = local_tools
    else:
        print(f"ℹ️  No gateway/auth header, using {len(local_tools)} local tools only")
    
    # Create agent with available tools
    try:
        agent = Agent(
            model=model, tools=tools, system_prompt=system_prompt
        )
        
        # Invoke agent
        response = agent(user_input)
        return response.message["content"][0]["text"]
    except Exception as e:
        print(f"Agent error: {str(e)}")
        return f"Error: {str(e)}"


if __name__ == "__main__":
    app.run()


if __name__ == "__main__":
    app.run()
