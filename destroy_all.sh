#!/bin/bash
set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                    Hertz MCP - Complete Teardown                        ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "⚠️  WARNING: This will delete ALL deployed resources!"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Teardown cancelled"
    exit 0
fi

# Get AWS credentials first (before loading .env which might override them)
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text || echo "")
export CDK_DEFAULT_REGION=$(aws configure get region || echo "us-east-1")

# Load environment variables (but preserve AWS credentials)
if [ -f .env ]; then
    # Load only non-AWS credential variables
    while IFS= read -r line; do
        if [[ ! "$line" =~ ^# ]] && [[ "$line" =~ ^[A-Z_]+=.+ ]]; then
            var_name=$(echo "$line" | cut -d'=' -f1)
            # Skip AWS credential variables to preserve current session
            if [[ "$var_name" != "AWS_ACCESS_KEY_ID" ]] && [[ "$var_name" != "AWS_SECRET_ACCESS_KEY" ]] && [[ "$var_name" != "AWS_SESSION_TOKEN" ]]; then
                export "$line"
            fi
        fi
    done < .env
    echo "✅ Loaded environment variables from .env"
fi

echo "✅ AWS Account: $CDK_DEFAULT_ACCOUNT"
echo "✅ AWS Region: $CDK_DEFAULT_REGION"

# Step 1: Destroy Frontend Stack
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1/5: Destroying Frontend Stack"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd frontend/react-app/cdk
echo "🗑️  Destroying HertzFrontendStack..."
cdk destroy --force || echo "⚠️  Frontend stack not found or already deleted"
echo "✅ Frontend stack destroyed"
cd ../../..

# Step 2: Delete AgentCore Runtime
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2/5: Deleting AgentCore Runtime"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get runtime ARN from SSM
RUNTIME_ARN=$(aws ssm get-parameter --name "/hertz/agentcore/strands_runtime_arn" --query "Parameter.Value" --output text || echo "")

if [ ! -z "$RUNTIME_ARN" ]; then
    echo "🗑️  Deleting runtime: $RUNTIME_ARN"
    
    # Extract runtime ID from ARN
    RUNTIME_ID=$(echo $RUNTIME_ARN | awk -F'/' '{print $NF}')
    
    # Delete the runtime
    aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id $RUNTIME_ID || echo "⚠️  Runtime not found or already deleted"
    
    # Wait for deletion
    echo "⏳ Waiting for runtime deletion..."
    sleep 10
    
    echo "✅ Runtime deleted"
else
    echo "⚠️  No runtime ARN found in SSM"
fi

# Step 3: Delete AgentCore Gateway
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3/5: Deleting AgentCore Gateway"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get gateway ID from SSM
GATEWAY_ID=$(aws ssm get-parameter --name "/hertz/agentcore/weather_gateway_id" --query "Parameter.Value" --output text || echo "")

if [ ! -z "$GATEWAY_ID" ]; then
    echo "🗑️  Deleting gateway: $GATEWAY_ID"
    
    # List and delete all targets first
    echo "🗑️  Deleting gateway targets..."
    TARGETS=$(aws bedrock-agentcore-control list-gateway-targets --gateway-identifier $GATEWAY_ID --query "items[].targetId" --output text || echo "")
    
    for TARGET_ID in $TARGETS; do
        echo "   Deleting target: $TARGET_ID"
        aws bedrock-agentcore-control delete-gateway-target --gateway-id $GATEWAY_ID --target-id $TARGET_ID || echo "   ⚠️  Target already deleted"
    done
    
    # Wait for targets to be deleted
    echo "⏳ Waiting for targets to be deleted..."
    sleep 5
    
    # Delete the gateway
    aws bedrock-agentcore-control delete-gateway --gateway-id $GATEWAY_ID || echo "⚠️  Gateway not found or already deleted"
    
    echo "✅ Gateway deleted"
else
    echo "⚠️  No gateway ID found in SSM"
fi

# Step 4: Clear DynamoDB Table
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4/5: Clearing DynamoDB Table"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗑️  DynamoDB table will be deleted with the CDK stack"
echo "✅ Skipping manual table cleanup"

# Step 5: Destroy Backend CDK Stacks
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 5/5: Destroying Backend CDK Stacks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd backend/cdk
echo "🗑️  Destroying HertzApiGatewayStack..."
cdk destroy HertzApiGatewayStack --force || echo "⚠️  API Gateway stack not found or already deleted"

echo "🗑️  Destroying HertzMcpStack..."
cdk destroy HertzMcpStack --force || echo "⚠️  MCP stack not found or already deleted"

echo "✅ Backend CDK stacks destroyed"
cd ../..

# Step 6: Clean up SSM Parameters
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 6/6: Cleaning up SSM Parameters"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SSM_PARAMS=(
    "/hertz/agentcore/weather_gateway_id"
    "/hertz/agentcore/weather_gateway_url"
    "/hertz/agentcore/weather_gateway_arn"
    "/hertz/agentcore/gateway_id"
    "/hertz/agentcore/strands_runtime_arn"
    "/hertz/agentcore/strands_runtime_url"
    "/hertz/agentcore/api_gateway_url"
    "/hertz/agentcore/cognito_user_pool_id"
    "/hertz/agentcore/cognito_client_id"
    "/hertz/agentcore/cognito_issuer"
    "/hertz/agentcore/cognito_identity_pool_id"
    "/hertz/agentcore/weather_lambda_arn"
    "/hertz/agentcore/flight_lambda_arn"
    "/hertz/agentcore/test_access_token"
)

echo "🗑️  Deleting SSM parameters..."
for PARAM in "${SSM_PARAMS[@]}"; do
    aws ssm delete-parameter --name "$PARAM" && echo "   ✅ Deleted: $PARAM" || echo "   ⚠️  Not found: $PARAM"
done

echo "✅ SSM parameters cleaned up"

# Step 7: Clean up local files
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 7/7: Cleaning up local files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Clean up CDK outputs
rm -rf backend/cdk/cdk.out
rm -rf frontend/react-app/cdk/cdk.out

# Clean up Docker artifacts from runtime deployment
rm -f backend/Dockerfile
rm -f backend/.dockerignore

# Clean up build artifacts
rm -rf frontend/react-app/build

echo "✅ Local files cleaned up"

# Final Summary
echo ""
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                     TEARDOWN COMPLETE! ✅                                 ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🗑️  Deleted Resources:"
echo "   ✅ Frontend CloudFront distribution and S3 bucket"
echo "   ✅ AgentCore Runtime (Docker container)"
echo "   ✅ AgentCore Gateway and targets"
echo "   ✅ API Gateway and Lambda proxy"
echo "   ✅ Backend Lambda functions"
echo "   ✅ DynamoDB Fleet Inventory table"
echo "   ✅ Cognito User Pool and Identity Pool"
echo "   ✅ IAM roles and policies"
echo "   ✅ SSM parameters"
echo "   ✅ Local build artifacts"
echo ""
echo "📝 Note: Your .env files have been preserved"
echo ""
echo "🎯 To redeploy everything, run: ./deploy_all.sh"
echo ""
