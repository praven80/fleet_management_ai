#!/bin/bash
set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                    Hertz MCP - Complete Deployment                      ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

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
else
    echo "⚠️  Warning: .env file not found"
fi

echo "✅ AWS Account: $CDK_DEFAULT_ACCOUNT"
echo "✅ AWS Region: $CDK_DEFAULT_REGION"

# Step 1: Deploy Backend CDK Stacks
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1/6: Deploying Backend CDK Stacks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd backend/cdk
echo "📦 Installing CDK dependencies..."
pip install -q -r requirements.txt
echo "🚀 Deploying HertzMcpStack and HertzApiGatewayStack..."
cdk deploy --all --require-approval never
if [ $? -ne 0 ]; then
    echo "❌ CDK deployment failed"
    exit 1
fi
echo "✅ Backend CDK stacks deployed successfully"
cd ../..

# Step 2: Deploy AgentCore Gateway
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2/6: Deploying AgentCore Gateway"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd backend
python deploy_gateway.py
if [ $? -ne 0 ]; then
    echo "❌ Gateway deployment failed"
    exit 1
fi
echo "✅ AgentCore Gateway deployed successfully"
cd ..

# Step 3: Load Fleet Data into DynamoDB
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3/6: Loading Fleet Data into DynamoDB"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd backend
python load_fleet_data.py
if [ $? -ne 0 ]; then
    echo "❌ Fleet data loading failed"
    exit 1
fi
echo "✅ Fleet data loaded successfully"
cd ..

# Step 4: Deploy AgentCore Runtime
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4/6: Deploying AgentCore Runtime"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check for existing runtime and delete if found
EXISTING_RUNTIME=$(aws bedrock-agentcore-control list-agent-runtimes --region us-east-1 --query "agentRuntimes[?agentRuntimeName=='hertz_strands_runtime'].agentRuntimeId" --output text 2>/dev/null || echo "")

if [ ! -z "$EXISTING_RUNTIME" ]; then
    echo "🗑️  Deleting existing runtime: $EXISTING_RUNTIME"
    aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id "$EXISTING_RUNTIME" --region us-east-1 2>/dev/null || echo "   ⚠️  Runtime already deleted or not found"
    
    # Wait for deletion to complete by checking if runtime still exists
    echo "⏳ Waiting for runtime deletion to complete..."
    for i in {1..24}; do
        RUNTIME_STATUS=$(aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id "$EXISTING_RUNTIME" --region us-east-1 --query "status" --output text 2>/dev/null || echo "NOT_FOUND")
        if [ "$RUNTIME_STATUS" = "NOT_FOUND" ]; then
            echo "✅ Runtime deleted successfully"
            break
        fi
        echo "   Status: $RUNTIME_STATUS (waiting 5s... attempt $i/24)"
        sleep 5
    done
    
    if [ "$RUNTIME_STATUS" != "NOT_FOUND" ]; then
        echo "⚠️  Warning: Runtime deletion taking longer than expected, continuing anyway..."
    fi
fi

cd backend
rm -f .bedrock_agentcore.yaml
python deploy_agentcore_runtime.py
if [ $? -ne 0 ]; then
    echo "❌ Runtime deployment failed"
    exit 1
fi
echo "✅ AgentCore Runtime deployed successfully"
cd ..

# Step 5: Update .env files with latest ARNs
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 5/6: Updating .env files with latest ARNs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get values from SSM Parameter Store
echo "📥 Retrieving configuration from AWS SSM..."
GATEWAY_URL=$(aws ssm get-parameter --name "/hertz/agentcore/weather_gateway_url" --query "Parameter.Value" --output text 2>/dev/null || echo "")
RUNTIME_ARN=$(aws ssm get-parameter --name "/hertz/agentcore/strands_runtime_arn" --query "Parameter.Value" --output text 2>/dev/null || echo "")
RUNTIME_URL=$(aws ssm get-parameter --name "/hertz/agentcore/strands_runtime_url" --query "Parameter.Value" --output text 2>/dev/null || echo "")
API_GATEWAY_URL=$(aws ssm get-parameter --name "/hertz/agentcore/api_gateway_url" --query "Parameter.Value" --output text 2>/dev/null || echo "")
COGNITO_USER_POOL_ID=$(aws ssm get-parameter --name "/hertz/agentcore/cognito_user_pool_id" --query "Parameter.Value" --output text 2>/dev/null || echo "")
COGNITO_CLIENT_ID=$(aws ssm get-parameter --name "/hertz/agentcore/cognito_client_id" --query "Parameter.Value" --output text 2>/dev/null || echo "")
COGNITO_IDENTITY_POOL_ID=$(aws ssm get-parameter --name "/hertz/agentcore/cognito_identity_pool_id" --query "Parameter.Value" --output text 2>/dev/null || echo "")

# Update root .env file
echo "📝 Updating root .env file..."
if [ ! -z "$GATEWAY_URL" ]; then
    if grep -q "^MCP_GATEWAY_URL=" .env; then
        sed -i.bak "s|^MCP_GATEWAY_URL=.*|MCP_GATEWAY_URL=$GATEWAY_URL|" .env
    else
        echo "MCP_GATEWAY_URL=$GATEWAY_URL" >> .env
    fi
fi

if [ ! -z "$RUNTIME_ARN" ]; then
    if grep -q "^STRANDS_RUNTIME_ARN=" .env; then
        sed -i.bak "s|^STRANDS_RUNTIME_ARN=.*|STRANDS_RUNTIME_ARN=$RUNTIME_ARN|" .env
    else
        echo "STRANDS_RUNTIME_ARN=$RUNTIME_ARN" >> .env
    fi
fi

if [ ! -z "$RUNTIME_URL" ]; then
    if grep -q "^STRANDS_RUNTIME_URL=" .env; then
        sed -i.bak "s|^STRANDS_RUNTIME_URL=.*|STRANDS_RUNTIME_URL=$RUNTIME_URL|" .env
    else
        echo "STRANDS_RUNTIME_URL=$RUNTIME_URL" >> .env
    fi
fi

# Update frontend .env file
echo "📝 Updating frontend .env file..."
FRONTEND_ENV="frontend/react-app/.env"

# Create frontend .env if it doesn't exist
if [ ! -f "$FRONTEND_ENV" ]; then
    echo "Creating $FRONTEND_ENV..."
    touch "$FRONTEND_ENV"
fi

# Update API Gateway URL (critical for fixing CORS issues)
if [ ! -z "$API_GATEWAY_URL" ]; then
    echo "   Setting REACT_APP_RUNTIME_ENDPOINT=${API_GATEWAY_URL}chat"
    if grep -q "^REACT_APP_RUNTIME_ENDPOINT=" "$FRONTEND_ENV"; then
        sed -i.bak "s|^REACT_APP_RUNTIME_ENDPOINT=.*|REACT_APP_RUNTIME_ENDPOINT=${API_GATEWAY_URL}chat|" "$FRONTEND_ENV"
    else
        echo "REACT_APP_RUNTIME_ENDPOINT=${API_GATEWAY_URL}chat" >> "$FRONTEND_ENV"
    fi
fi

# Update Cognito configuration
if [ ! -z "$COGNITO_USER_POOL_ID" ]; then
    echo "   Setting REACT_APP_COGNITO_USER_POOL_ID=$COGNITO_USER_POOL_ID"
    if grep -q "^REACT_APP_COGNITO_USER_POOL_ID=" "$FRONTEND_ENV"; then
        sed -i.bak "s|^REACT_APP_COGNITO_USER_POOL_ID=.*|REACT_APP_COGNITO_USER_POOL_ID=$COGNITO_USER_POOL_ID|" "$FRONTEND_ENV"
    else
        echo "REACT_APP_COGNITO_USER_POOL_ID=$COGNITO_USER_POOL_ID" >> "$FRONTEND_ENV"
    fi
fi

if [ ! -z "$COGNITO_CLIENT_ID" ]; then
    echo "   Setting REACT_APP_COGNITO_CLIENT_ID=$COGNITO_CLIENT_ID"
    if grep -q "^REACT_APP_COGNITO_CLIENT_ID=" "$FRONTEND_ENV"; then
        sed -i.bak "s|^REACT_APP_COGNITO_CLIENT_ID=.*|REACT_APP_COGNITO_CLIENT_ID=$COGNITO_CLIENT_ID|" "$FRONTEND_ENV"
    else
        echo "REACT_APP_COGNITO_CLIENT_ID=$COGNITO_CLIENT_ID" >> "$FRONTEND_ENV"
    fi
fi

if [ ! -z "$COGNITO_IDENTITY_POOL_ID" ]; then
    echo "   Setting REACT_APP_COGNITO_IDENTITY_POOL_ID=$COGNITO_IDENTITY_POOL_ID"
    if grep -q "^REACT_APP_COGNITO_IDENTITY_POOL_ID=" "$FRONTEND_ENV"; then
        sed -i.bak "s|^REACT_APP_COGNITO_IDENTITY_POOL_ID=.*|REACT_APP_COGNITO_IDENTITY_POOL_ID=$COGNITO_IDENTITY_POOL_ID|" "$FRONTEND_ENV"
    else
        echo "REACT_APP_COGNITO_IDENTITY_POOL_ID=$COGNITO_IDENTITY_POOL_ID" >> "$FRONTEND_ENV"
    fi
fi

# Add AWS region
echo "   Setting REACT_APP_AWS_REGION=${AWS_REGION:-us-east-1}"
if grep -q "^REACT_APP_AWS_REGION=" "$FRONTEND_ENV"; then
    sed -i.bak "s|^REACT_APP_AWS_REGION=.*|REACT_APP_AWS_REGION=${AWS_REGION:-us-east-1}|" "$FRONTEND_ENV"
else
    echo "REACT_APP_AWS_REGION=${AWS_REGION:-us-east-1}" >> "$FRONTEND_ENV"
fi

# Clean up backup files
rm -f .env.bak "$FRONTEND_ENV.bak"

echo "✅ Environment files updated successfully"
echo ""
echo "📋 Frontend configuration:"
cat "$FRONTEND_ENV"

# Step 6: Deploy Frontend
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 6/6: Deploying Frontend to CloudFront"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd frontend/react-app

# Install dependencies
echo "📦 Installing frontend dependencies..."
npm install

# Build React app
echo "🔨 Building React app..."
npm run build

# Deploy frontend CDK stack
echo "🚀 Deploying frontend CDK stack..."
cd cdk
pip install -q -r requirements.txt
cdk deploy --require-approval never
if [ $? -ne 0 ]; then
    echo "❌ Frontend CDK deployment failed"
    exit 1
fi

# Get CloudFront distribution details
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name HertzFrontendStack --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" --output text)
DISTRIBUTION_ID=$(aws cloudformation describe-stacks --stack-name HertzFrontendStack --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue" --output text)
CLOUDFRONT_URL=$(aws cloudformation describe-stacks --stack-name HertzFrontendStack --query "Stacks[0].Outputs[?OutputKey=='CloudFrontURL'].OutputValue" --output text)

# Upload build files to S3
echo "📤 Uploading build files to S3..."
cd ..
aws s3 sync build/ s3://$BUCKET_NAME/ --delete

# Invalidate CloudFront cache
echo "🔄 Invalidating CloudFront cache..."
aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"

echo "✅ Frontend deployed successfully"
cd ../..

# Get the latest runtime ARN for display
DEPLOYED_RUNTIME_ARN=$(aws ssm get-parameter --name "/hertz/agentcore/strands_runtime_arn" --query "Parameter.Value" --output text 2>/dev/null || echo "")

# Final Summary
echo ""
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                     DEPLOYMENT COMPLETE! ✅                               ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Deployed Resources:"
echo "   ✅ Backend CDK Stacks (Lambda, DynamoDB, Cognito, IAM)"
echo "   ✅ AgentCore Gateway with Weather & Flight tools"
echo "   ✅ DynamoDB Fleet Inventory (populated with mock data)"
echo "   ✅ AgentCore Runtime (Docker container)"
echo "   ✅ API Gateway for React app"
echo "   ✅ Frontend React app on CloudFront"
echo ""
echo "🌐 Access URLs:"
echo "   Frontend: $CLOUDFRONT_URL"
echo "   API Gateway: $API_GATEWAY_URL"
echo "   Gateway URL: $GATEWAY_URL"
echo ""
echo "🔑 Test Credentials:"
echo "   Username: ${COGNITO_TEST_USERNAME:-test-user}"
echo "   Password: ${COGNITO_TEST_PASSWORD:-TestPass123!}"
echo ""
echo "📝 Configuration stored in:"
echo "   - .env (backend)"
echo "   - frontend/react-app/.env (frontend)"
echo "   - AWS SSM Parameter Store"
echo ""
echo "⚠️  MANUAL ACTION REQUIRED:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Update Lambda Runtime ARN:"
echo ""
echo "   Run this command to update the Lambda function with the new runtime ARN:"
echo ""
if [ ! -z "$DEPLOYED_RUNTIME_ARN" ]; then
    echo "   aws lambda update-function-configuration \\"
    echo "     --function-name hertz-runtime-proxy \\"
    echo "     --environment Variables=\"{STRANDS_RUNTIME_ARN=$DEPLOYED_RUNTIME_ARN,COGNITO_USER_POOL_ID=$COGNITO_USER_POOL_ID,COGNITO_CLIENT_ID=$COGNITO_CLIENT_ID,COGNITO_TEST_USERNAME=${COGNITO_TEST_USERNAME:-test-user},COGNITO_TEST_PASSWORD=${COGNITO_TEST_PASSWORD:-TestPass123!},TICKETMASTER_API_KEY=${TICKETMASTER_API_KEY:-},AVIATIONSTACK_API_KEY=${AVIATIONSTACK_API_KEY:-}}\""
    echo ""
    echo "   Or copy this ARN to update manually in AWS Console:"
    echo "   $DEPLOYED_RUNTIME_ARN"
else
    echo "   ⚠️  Could not retrieve runtime ARN from SSM"
fi
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎯 Next Steps:"
echo "   1. Update the Lambda function with the command above"
echo "   2. Open the frontend URL in your browser"
echo "   3. Sign in with the test credentials"
echo "   4. Start chatting with the AI agent!"
echo ""
