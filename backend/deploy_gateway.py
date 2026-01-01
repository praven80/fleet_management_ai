#!/usr/bin/env python3
"""
Deploy AgentCore Gateway using boto3
This runs after CDK deployment to create the gateway
"""
import boto3
import json
import sys
import time
import os

def main():
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║         AgentCore Gateway Deployment - Weather + Flight Tools           ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝\n")
    
    region = "us-east-1"
    
    # Get stack outputs
    cfn = boto3.client("cloudformation", region_name=region)
    
    try:
        stack = cfn.describe_stacks(StackName="HertzMcpStack")
        outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Stacks"][0]["Outputs"]}
        
        weather_lambda_arn = outputs["WeatherLambdaArn"]
        flight_lambda_arn = outputs["FlightLambdaArn"]
        gateway_role_arn = outputs["GatewayRoleArn"]
        cognito_user_pool_id = outputs["CognitoUserPoolId"]
        cognito_client_id = outputs["CognitoClientId"]
        cognito_issuer = outputs["CognitoIssuer"]
        
        print(f"✅ Retrieved CDK outputs:")
        print(f"   Weather Lambda ARN: {weather_lambda_arn}")
        print(f"   Flight Lambda ARN: {flight_lambda_arn}")
        print(f"   Gateway Role ARN: {gateway_role_arn}")
        print(f"   Cognito User Pool: {cognito_user_pool_id}")
        print(f"   Cognito Client: {cognito_client_id}")
    except Exception as e:
        print(f"❌ Error: Could not find HertzMcpStack")
        print(f"   Please run: ./deploy_cdk.sh first")
        print(f"   Error: {e}")
        sys.exit(1)
    
    # Initialize clients
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)
    ssm = boto3.client("ssm", region_name=region)
    cognito_client = boto3.client("cognito-idp", region_name=region)
    
    # Load API specs (MCP format)
    with open("lambda/weather_api_spec.json", "r") as f:
        weather_api_spec = json.load(f)
    
    with open("lambda/flight_api_spec_mcp.json", "r") as f:
        flight_api_spec = json.load(f)
    
    # Check if gateway already exists
    print("\n[1/3] Checking for existing gateway...")
    try:
        gateway_id_param = ssm.get_parameter(Name="/hertz/agentcore/weather_gateway_id")
        gateway_id = gateway_id_param["Parameter"]["Value"]
        
        # Verify it exists
        gateway_info = gateway_client.get_gateway(gatewayIdentifier=gateway_id)
        gateway_url = gateway_info["gatewayUrl"]
        gateway_arn = gateway_info["gatewayArn"]
        
        print(f"✅ Gateway already exists: {gateway_id}")
        print(f"   URL: {gateway_url}")
    except (ssm.exceptions.ParameterNotFound, gateway_client.exceptions.ResourceNotFoundException):
        print("🔧 Creating new gateway...")
        
        # Create gateway
        # Configure JWT authorizer with Cognito
        auth_config = {
            "customJWTAuthorizer": {
                "allowedClients": [cognito_client_id],
                "discoveryUrl": f"{cognito_issuer}/.well-known/openid-configuration",
            }
        }
        
        gateway_response = gateway_client.create_gateway(
            name="hertz-mcp-gateway",
            roleArn=gateway_role_arn,
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration=auth_config,
            description="Hertz MCP Gateway - Weather + Flight Traffic Tools with Cognito Auth"
        )
        
        gateway_id = gateway_response["gatewayId"]
        gateway_url = gateway_response["gatewayUrl"]
        gateway_arn = gateway_response["gatewayArn"]
        
        print(f"✅ Gateway created: {gateway_id}")
        print(f"   URL: {gateway_url}")
        
        # Store in SSM
        ssm.put_parameter(
            Name="/hertz/agentcore/weather_gateway_id",
            Value=gateway_id,
            Type="String",
            Overwrite=True
        )
        ssm.put_parameter(
            Name="/hertz/agentcore/weather_gateway_url",
            Value=gateway_url,
            Type="String",
            Overwrite=True
        )
        ssm.put_parameter(
            Name="/hertz/agentcore/weather_gateway_arn",
            Value=gateway_arn,
            Type="String",
            Overwrite=True
        )
        # Also store as gateway_id for runtime compatibility
        ssm.put_parameter(
            Name="/hertz/agentcore/gateway_id",
            Value=gateway_id,
            Type="String",
            Overwrite=True
        )
        print("✅ Configuration stored in SSM")
        
        # Wait for gateway to be ACTIVE
        print("⏳ Waiting for gateway to become ACTIVE...")
        max_wait_time = 300  # 5 minutes
        wait_interval = 10  # 10 seconds
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                gateway_info = gateway_client.get_gateway(gatewayIdentifier=gateway_id)
                status = gateway_info.get("status")
                
                if status in ["ACTIVE", "READY"]:
                    print(f"✅ Gateway is now {status}")
                    break
                elif status in ["FAILED", "DELETING", "DELETED"]:
                    print(f"❌ Gateway entered {status} state")
                    sys.exit(1)
                else:
                    print(f"   Status: {status} (waiting {wait_interval}s...)")
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval
            except Exception as e:
                print(f"⚠️  Error checking gateway status: {e}")
                time.sleep(wait_interval)
                elapsed_time += wait_interval
        
        if elapsed_time >= max_wait_time:
            print(f"⚠️  Gateway did not become READY within {max_wait_time}s")
            print(f"   You may need to run this script again to create targets")
    
    # Add Lambda targets
    print("\n[2/3] Configuring gateway targets...")
    
    # Weather target
    try:
        targets = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        existing_weather_target = None
        for target in targets.get("items", []):
            if target["name"] == "WeatherForecastTool":
                existing_weather_target = target["targetId"]
                break
        
        if existing_weather_target:
            print(f"✅ Weather target already exists: {existing_weather_target}")
        else:
            print("🔧 Creating weather target...")
            
            target_response = gateway_client.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name="WeatherForecastTool",
                description="Weather forecast tool for demand prediction",
                targetConfiguration={
                    "mcp": {
                        "lambda": {
                            "lambdaArn": weather_lambda_arn,
                            "toolSchema": {"inlinePayload": weather_api_spec}
                        }
                    }
                },
                credentialProviderConfigurations=[
                    {"credentialProviderType": "GATEWAY_IAM_ROLE"}
                ]
            )
            
            target_id = target_response["targetId"]
            print(f"✅ Weather target created: {target_id}")
    except Exception as e:
        print(f"⚠️  Error with weather target: {e}")
    
    # Flight target
    try:
        targets = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        existing_flight_target = None
        for target in targets.get("items", []):
            if target["name"] == "FlightTrafficTool":
                existing_flight_target = target["targetId"]
                break
        
        if existing_flight_target:
            print(f"✅ Flight target already exists: {existing_flight_target}")
        else:
            print("🔧 Creating flight target...")
            
            target_response = gateway_client.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name="FlightTrafficTool",
                description="Flight traffic tool for airport demand prediction",
                targetConfiguration={
                    "mcp": {
                        "lambda": {
                            "lambdaArn": flight_lambda_arn,
                            "toolSchema": {"inlinePayload": flight_api_spec}
                        }
                    }
                },
                credentialProviderConfigurations=[
                    {"credentialProviderType": "GATEWAY_IAM_ROLE"}
                ]
            )
            
            target_id = target_response["targetId"]
            print(f"✅ Flight target created: {target_id}")
    except Exception as e:
        print(f"⚠️  Error with flight target: {e}")
    
    # Create test user
    print("\n[3/5] Creating Cognito test user...")
    test_username = "test-user"
    test_password = "TestPass123!"
    test_email = "test@example.com"
    
    try:
        # Check if user exists
        cognito_client.admin_get_user(
            UserPoolId=cognito_user_pool_id,
            Username=test_username
        )
        print(f"✅ Test user already exists: {test_username}")
    except cognito_client.exceptions.UserNotFoundException:
        print(f"🔧 Creating test user: {test_username}")
        
        # Create user
        cognito_client.admin_create_user(
            UserPoolId=cognito_user_pool_id,
            Username=test_username,
            UserAttributes=[
                {"Name": "email", "Value": test_email},
                {"Name": "email_verified", "Value": "true"}
            ],
            TemporaryPassword=test_password,
            MessageAction="SUPPRESS"
        )
        
        # Set permanent password
        cognito_client.admin_set_user_password(
            UserPoolId=cognito_user_pool_id,
            Username=test_username,
            Password=test_password,
            Permanent=True
        )
        
        print(f"✅ Test user created")
        print(f"   Username: {test_username}")
        print(f"   Password: {test_password}")
    
    # Get access token for the test user
    print("\n[4/5] Getting access token...")
    try:
        auth_response = cognito_client.admin_initiate_auth(
            UserPoolId=cognito_user_pool_id,
            ClientId=cognito_client_id,
            AuthFlow="ADMIN_USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": test_username,
                "PASSWORD": test_password
            }
        )
        
        access_token = auth_response["AuthenticationResult"]["AccessToken"]
        id_token = auth_response["AuthenticationResult"]["IdToken"]
        
        print(f"✅ Access token obtained")
        
        # Store token in SSM for easy retrieval
        ssm.put_parameter(
            Name="/hertz/agentcore/test_access_token",
            Value=access_token,
            Type="SecureString",
            Overwrite=True
        )
        print(f"✅ Token stored in SSM")
    except Exception as e:
        print(f"⚠️  Error getting token: {e}")
        access_token = None
    
    # Update .env file
    print("\n[5/5] Updating .env file...")
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    with open(env_path, "r") as f:
        env_content = f.read()
    
    env_updates = []
    if "MCP_GATEWAY_URL" not in env_content:
        env_updates.append(f"MCP_GATEWAY_URL={gateway_url}")
    if "WEATHER_LAMBDA_ARN" not in env_content:
        env_updates.append(f"WEATHER_LAMBDA_ARN={weather_lambda_arn}")
    if "FLIGHT_LAMBDA_ARN" not in env_content:
        env_updates.append(f"FLIGHT_LAMBDA_ARN={flight_lambda_arn}")
    if "COGNITO_USER_POOL_ID" not in env_content:
        env_updates.append(f"COGNITO_USER_POOL_ID={cognito_user_pool_id}")
    if "COGNITO_CLIENT_ID" not in env_content:
        env_updates.append(f"COGNITO_CLIENT_ID={cognito_client_id}")
    if "COGNITO_TEST_USERNAME" not in env_content:
        env_updates.append(f"COGNITO_TEST_USERNAME={test_username}")
    if "COGNITO_TEST_PASSWORD" not in env_content:
        env_updates.append(f"COGNITO_TEST_PASSWORD={test_password}")
    
    if env_updates:
        with open(env_path, "a") as f:
            f.write("\n\n# MCP Gateway Configuration (Deployed)\n")
            for update in env_updates:
                f.write(f"{update}\n")
        print(f"✅ Added {len(env_updates)} configuration(s) to .env")
    else:
        print("✅ .env already up to date")
    
    print("\n╔══════════════════════════════════════════════════════════════════════════╗")
    print("║                        DEPLOYMENT COMPLETE! ✅                            ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print(f"\n📊 Deployed Resources:")
    print(f"   ✅ Lambda Functions:")
    print(f"      - hertz-weather-forecast")
    print(f"      - hertz-flight-traffic")
    print(f"   ✅ Gateway ID: {gateway_id}")
    print(f"   ✅ Gateway URL: {gateway_url}")
    print(f"   ✅ Gateway Targets:")
    print(f"      - WeatherForecastTool")
    print(f"      - FlightTrafficTool")
    print(f"   ✅ Cognito User Pool: {cognito_user_pool_id}")
    print(f"   ✅ Test User: {test_username}")
    print(f"\n🔑 Test Credentials:")
    print(f"   Username: {test_username}")
    print(f"   Password: {test_password}")
    print(f"\n🎯 Next Steps:")
    print(f"   1. Test: python test_mcp_weather.py")
    print(f"   2. Run app: streamlit run app.py")
    print(f"\n🗑️  To remove everything:")
    print(f"   python destroy_all.py")
    print()

if __name__ == "__main__":
    main()
