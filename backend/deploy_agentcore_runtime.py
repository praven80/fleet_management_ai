"""
Deploy Strands Agent to Amazon Bedrock AgentCore Runtime
This script deploys the agent as a production-ready, scalable service
"""
import boto3
import time
import os
import json
from dotenv import load_dotenv

load_dotenv(".env")

# Check if bedrock_agentcore_starter_toolkit is available
try:
    from bedrock_agentcore_starter_toolkit import Runtime
    print("✅ AgentCore Starter Toolkit found")
except ImportError:
    print("❌ bedrock_agentcore_starter_toolkit not found")
    print("   Install it with: pip install bedrock-agentcore-starter-toolkit")
    exit(1)


def get_ssm_parameter(name: str) -> str:
    """Retrieve parameter from AWS Systems Manager Parameter Store"""
    ssm = boto3.client('ssm')
    try:
        response = ssm.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        return None


def put_ssm_parameter(name: str, value: str) -> str:
    """Store parameter in AWS Systems Manager Parameter Store"""
    ssm = boto3.client('ssm')
    try:
        ssm.put_parameter(
            Name=name,
            Value=value,
            Type='String',
            Overwrite=True
        )
        print(f"✅ Stored parameter: {name}")
        return value
    except Exception as e:
        print(f"⚠️  Error storing parameter {name}: {e}")
        return None


def create_execution_role():
    """Create IAM execution role for AgentCore Runtime"""
    iam = boto3.client('iam')
    role_name = "HertzStrandsAgentCoreRuntimeRole"
    
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    try:
        # Try to get existing role
        response = iam.get_role(RoleName=role_name)
        role_arn = response['Role']['Arn']
        print(f"✅ Using existing role: {role_arn}")
        
        # Ensure all policies are attached (in case of partial deployment)
        _attach_policies(iam, role_name)
        
        return role_arn
    except iam.exceptions.NoSuchEntityException:
        # Create new role
        print(f"Creating IAM role: {role_name}")
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Execution role for Hertz Strands AgentCore Runtime"
        )
        role_arn = response['Role']['Arn']
        
        # Attach all necessary policies
        _attach_policies(iam, role_name)
        
        print(f"✅ Created role: {role_arn}")
        print("   Waiting 10 seconds for IAM propagation...")
        time.sleep(10)
        
        return role_arn


def _attach_policies(iam, role_name):
    """Attach all necessary policies to the runtime role"""
    # AWS managed policies
    managed_policies = [
        "arn:aws:iam::aws:policy/AmazonBedrockFullAccess",
        "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
        "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess",
        "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        "arn:aws:iam::aws:policy/AmazonDynamoDBReadOnlyAccess"
    ]
    
    for policy_arn in managed_policies:
        try:
            iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print(f"  ✅ Attached: {policy_arn.split('/')[-1]}")
        except iam.exceptions.NoSuchEntityException:
            print(f"  ⚠️  Policy not found: {policy_arn}")
        except Exception as e:
            if "already attached" not in str(e).lower():
                print(f"  ⚠️  Error attaching {policy_arn}: {e}")
    
    # Custom inline policy for Gateway access
    gateway_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetGateway",
                    "bedrock-agentcore:InvokeGateway"
                ],
                "Resource": "*"
            }
        ]
    }
    
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="GatewayAccess",
            PolicyDocument=json.dumps(gateway_policy)
        )
        print(f"  ✅ Attached: GatewayAccess (inline)")
    except Exception as e:
        print(f"  ⚠️  Error attaching inline policy: {e}")


def main():
    print("=" * 60)
    print("Deploying Strands Agent to AgentCore Runtime")
    print("=" * 60)
    
    # Initialize boto session
    boto_session = boto3.session.Session()
    region = boto_session.region_name
    print(f"\n📍 Region: {region}")
    
    # Create execution role
    print("\n1️⃣  Creating/verifying IAM execution role...")
    execution_role_arn = create_execution_role()
    
    # Initialize runtime
    print("\n2️⃣  Initializing AgentCore Runtime...")
    # Change to backend directory for proper entrypoint resolution
    import os
    original_dir = os.getcwd()
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(backend_dir)
    agentcore_runtime = Runtime()
    
    # Configure the deployment
    print("\n3️⃣  Configuring deployment...")
    
    # Get Cognito configuration from CDK outputs
    try:
        cfn = boto3.client("cloudformation", region_name=region)
        stack = cfn.describe_stacks(StackName="HertzMcpStack")
        outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Stacks"][0]["Outputs"]}
        cognito_user_pool_id = outputs.get("CognitoUserPoolId")
        cognito_client_id = outputs.get("CognitoClientId")
        print(f"   Retrieved Cognito config from CDK:")
        print(f"   - User Pool: {cognito_user_pool_id}")
        print(f"   - Client ID: {cognito_client_id}")
    except Exception as e:
        print(f"   ⚠️  Could not get Cognito from CDK, trying environment variables...")
        cognito_client_id = os.getenv("COGNITO_CLIENT_ID")
        cognito_user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
    
    config_params = {
        "entrypoint": "strands_runtime.py",
        "execution_role": execution_role_arn,
        "auto_create_ecr": True,
        "region": region,
        "agent_name": "hertz_strands_runtime"
    }
    
    # Use IAM authorization for Lambda invocation (not Cognito)
    # This allows the Lambda proxy to invoke the runtime using its IAM role
    print(f"   Configuring IAM (SigV4) authorization for Lambda access")
    
    response = agentcore_runtime.configure(**config_params)
    print(f"✅ Configuration complete")
    
    # Inject API keys into the generated Dockerfile
    dockerfile_path = os.path.join(backend_dir, "Dockerfile")
    if os.path.exists(dockerfile_path):
        with open(dockerfile_path, "r") as f:
            dockerfile_content = f.read()
        
        # Find the ENV section and add our API keys
        if "ENV AWS_REGION" in dockerfile_content and "TICKETMASTER_API_KEY" not in dockerfile_content:
            # Add API keys after AWS_REGION
            dockerfile_content = dockerfile_content.replace(
                "ENV AWS_REGION=us-east-1\nENV AWS_DEFAULT_REGION=us-east-1",
                "ENV AWS_REGION=us-east-1\nENV AWS_DEFAULT_REGION=us-east-1\n\n# API Keys\nENV TICKETMASTER_API_KEY=ovM0gHqGMvcrzDbhtuT87VCxpYd0ioLA\nENV AVIATIONSTACK_API_KEY=24de2d517415e5f9b723203ecb288daf"
            )
            
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)
            print(f"✅ Injected API keys into Dockerfile")
    
    # Prepare environment variables
    env_vars = {
        "AWS_REGION": region,
    }
    
    # Add optional environment variables if they exist
    optional_vars = [
        "MCP_GATEWAY_URL",
        "COGNITO_USER_POOL_ID",
        "COGNITO_CLIENT_ID",
        "COGNITO_TEST_USERNAME",
        "COGNITO_TEST_PASSWORD",
        "TICKETMASTER_API_KEY",
        "AVIATIONSTACK_API_KEY"
    ]
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            env_vars[var] = value
    
    print(f"\n4️⃣  Launching agent runtime...")
    print("   This will build and deploy a Docker container (may take 5-10 minutes)...")
    
    try:
        launch_result = agentcore_runtime.launch(env_vars=env_vars)
        agent_arn = launch_result.agent_arn
        print(f"\n✅ Launch initiated!")
        print(f"   Agent ARN: {agent_arn}")
        
        # Store ARN in SSM
        put_ssm_parameter("/hertz/agentcore/strands_runtime_arn", agent_arn)
        
        # Wait for deployment to complete
        print(f"\n5️⃣  Waiting for deployment to complete...")
        status_response = agentcore_runtime.status()
        status = status_response.endpoint["status"]
        
        end_status = ["READY", "CREATE_FAILED", "DELETE_FAILED", "UPDATE_FAILED"]
        while status not in end_status:
            print(f"   Status: {status} (checking again in 10 seconds...)")
            time.sleep(10)
            status_response = agentcore_runtime.status()
            status = status_response.endpoint["status"]
        
        print(f"\n✅ Final status: {status}")
        
        if status == "READY":
            # Get endpoint URL
            endpoint_url = status_response.endpoint.get("url", "N/A")
            print(f"\n🎉 Deployment successful!")
            print(f"   Endpoint URL: {endpoint_url}")
            
            # Store endpoint URL in SSM
            if endpoint_url != "N/A":
                put_ssm_parameter("/hertz/agentcore/strands_runtime_url", endpoint_url)
            
            # Update .bedrock_agentcore.yaml with the new runtime ARN
            import yaml
            # Look for config in backend directory (where it's generated)
            config_path = os.path.join(backend_dir, ".bedrock_agentcore.yaml")
            try:
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        config = yaml.safe_load(f)
                    
                    # Extract runtime ID from ARN
                    runtime_id = agent_arn.split("/")[-1]
                    
                    # Update the agent configuration
                    agent_name = "hertz_strands_runtime"
                    if agent_name in config.get("agents", {}):
                        config["agents"][agent_name]["bedrock_agentcore"]["agent_id"] = runtime_id
                        config["agents"][agent_name]["bedrock_agentcore"]["agent_arn"] = agent_arn
                        config["agents"][agent_name]["bedrock_agentcore"]["agent_session_id"] = None
                        
                        with open(config_path, "w") as f:
                            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                        
                        print(f"✅ Updated .bedrock_agentcore.yaml with runtime ARN")
                else:
                    print(f"ℹ️  No .bedrock_agentcore.yaml found (this is normal for fresh deployments)")
            except Exception as e:
                print(f"⚠️  Could not update .bedrock_agentcore.yaml: {e}")
            
            print(f"\n📝 Next steps:")
            print(f"   1. Update your .env file with:")
            print(f"      STRANDS_RUNTIME_ARN={agent_arn}")
            print(f"      STRANDS_RUNTIME_URL={endpoint_url}")
            print(f"   2. Run the Streamlit app: streamlit run app.py")
            print(f"   3. Monitor in CloudWatch: https://console.aws.amazon.com/cloudwatch/")
        else:
            print(f"\n❌ Deployment failed with status: {status}")
            print(f"   Check CloudWatch logs for details")
    
    except Exception as e:
        print(f"\n❌ Error during deployment: {e}")
        print(f"   Check your AWS credentials and permissions")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
