"""
Lambda function to proxy requests from React app to AgentCore Runtime
This enables the React app to use all AgentCore features including MCP tools
"""
import json
import os
import boto3

# Initialize clients
# AWS_REGION is automatically set by Lambda runtime
region = os.environ['AWS_REGION']
cognito_client = boto3.client('cognito-idp', region_name=region)

# Runtime configuration
COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID')
COGNITO_CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID')
TEST_USERNAME = os.environ.get('COGNITO_TEST_USERNAME', 'test-user')
TEST_PASSWORD = os.environ.get('COGNITO_TEST_PASSWORD')
RUNTIME_ARN = os.environ.get('STRANDS_RUNTIME_ARN')


def get_cognito_token():
    """Get Cognito access token for runtime authentication"""
    try:
        auth_response = cognito_client.admin_initiate_auth(
            UserPoolId=COGNITO_USER_POOL_ID,
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow='ADMIN_USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': TEST_USERNAME,
                'PASSWORD': TEST_PASSWORD,
            },
        )
        return auth_response['AuthenticationResult']['AccessToken']
    except Exception as e:
        print(f'Error getting Cognito token: {e}')
        return None


def invoke_runtime(prompt, token):
    """Invoke AgentCore Runtime using boto3 with IAM auth (no HTTP/bearer token needed)"""
    try:
        import json
        import uuid
        
        # Use boto3 bedrock-agentcore client with IAM credentials
        # This works from Lambda without needing internet access
        client = boto3.client('bedrock-agentcore', region_name=region)
        
        runtime_id = RUNTIME_ARN.split('/')[-1]
        session_id = str(uuid.uuid4())
        
        print(f"Invoking runtime: {runtime_id}")
        print(f"Session ID: {session_id}")
        print(f"Prompt: {prompt[:100]}")
        
        # Invoke using boto3 SDK (uses IAM auth, not bearer token)
        # Parameters based on bedrock-agentcore API
        response = client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            payload=json.dumps({"prompt": prompt}),
            runtimeSessionId=session_id
        )
        
        # Extract response from the streaming body
        if 'response' in response and hasattr(response['response'], 'read'):
            # It's a StreamingBody object
            response_bytes = response['response'].read()
            response_data = json.loads(response_bytes.decode('utf-8'))
            # Check if response_data is a dict or string
            if isinstance(response_data, dict):
                response_text = response_data.get('response', str(response_data))
            else:
                response_text = response_data
        elif 'outputText' in response:
            response_text = response['outputText']
        elif 'completion' in response:
            # Handle streaming response
            response_text = ""
            for event in response['completion']:
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        response_text += chunk['bytes'].decode('utf-8')
        else:
            response_text = str(response)
        
        print(f"Extracted response: {response_text[:200]}")
        
        # Clean up response
        response_text = response_text.strip()
        if (response_text.startswith('"') and response_text.endswith('"')) or \
           (response_text.startswith("'") and response_text.endswith("'")):
            response_text = response_text[1:-1]
        response_text = response_text.replace('\\n', '\n')
        
        return response_text if response_text else "No response from runtime"
        
    except Exception as e:
        print(f'Error invoking runtime: {e}')
        import traceback
        traceback.print_exc()
        return None


def lambda_handler(event, context):
    """Lambda handler for API Gateway requests"""
    
    # Common CORS headers
    cors_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'POST,OPTIONS'
    }
    
    # Handle OPTIONS request for CORS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': ''
        }
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        prompt = body.get('prompt', '')
        
        if not prompt:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'No prompt provided'})
            }
        
        # Get Cognito token
        token = get_cognito_token()
        if not token:
            return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Failed to authenticate'})
            }
        
        # Invoke runtime
        response_text = invoke_runtime(prompt, token)
        
        if response_text:
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({'response': response_text})
            }
        else:
            return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Failed to get response from runtime'})
            }
    
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': str(e)})
        }
