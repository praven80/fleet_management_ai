#!/bin/bash
set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                    Hertz MCP - Frontend Deployment                      ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# Get AWS credentials
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text || echo "")
export CDK_DEFAULT_REGION=$(aws configure get region || echo "us-east-1")

echo "✅ AWS Account: $CDK_DEFAULT_ACCOUNT"
echo "✅ AWS Region: $CDK_DEFAULT_REGION"
echo ""

# Navigate to frontend directory
cd frontend/react-app

# Step 1: Install dependencies (if needed)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1/4: Installing dependencies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ ! -d "node_modules" ]; then
    echo "📦 Installing npm packages..."
    npm install
else
    echo "✅ Dependencies already installed"
fi
echo ""

# Step 2: Build React app
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2/4: Building React app"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔨 Building production bundle..."
npm run build
echo "✅ Build complete"
echo ""

# Step 3: Get S3 bucket and CloudFront distribution from CDK outputs
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3/4: Uploading to S3"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get bucket name from CDK stack
cd cdk
BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name HertzFrontendStack \
    --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" \
    --output text)

DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name HertzFrontendStack \
    --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue" \
    --output text)

cd ..

if [ -z "$BUCKET_NAME" ]; then
    echo "❌ Could not find S3 bucket. Make sure HertzFrontendStack is deployed."
    exit 1
fi

echo "📤 Uploading to S3 bucket: $BUCKET_NAME"
aws s3 sync build/ s3://$BUCKET_NAME/ --delete
echo "✅ Upload complete"
echo ""

# Step 4: Invalidate CloudFront cache
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4/4: Invalidating CloudFront cache"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -z "$DISTRIBUTION_ID" ]; then
    echo "⚠️  Could not find CloudFront distribution ID. Skipping cache invalidation."
else
    echo "🔄 Invalidating CloudFront distribution: $DISTRIBUTION_ID"
    aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"
    echo "✅ Cache invalidation initiated"
fi

cd ../..

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                     FRONTEND DEPLOYMENT COMPLETE! ✅                      ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 Your frontend is now live!"
echo ""
echo "📝 Note: CloudFront cache invalidation may take a few minutes to propagate."
echo "    If you don't see changes immediately, wait 2-3 minutes and refresh."
echo ""
