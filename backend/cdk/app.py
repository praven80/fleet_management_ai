#!/usr/bin/env python3
"""
AWS CDK App for Hertz MCP Tools Infrastructure
"""
import os
from aws_cdk import App, Environment
from hertz_mcp_stack import HertzMcpStack
from api_gateway_stack import ApiGatewayStack

# Get AWS account and region from environment
account = os.environ.get("CDK_DEFAULT_ACCOUNT", os.environ.get("AWS_ACCOUNT_ID"))
region = os.environ.get("CDK_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-east-1"))

app = App()

env = Environment(account=account, region=region)

# Deploy main stack first
main_stack = HertzMcpStack(
    app,
    "HertzMcpStack",
    env=env,
    description="Hertz MCP Tools with AgentCore Gateway and Lambda functions"
)

# Deploy API Gateway stack for React app
api_stack = ApiGatewayStack(
    app,
    "HertzApiGatewayStack",
    env=env,
    description="API Gateway + Lambda proxy for React app to invoke AgentCore Runtime"
)
api_stack.add_dependency(main_stack)

app.synth()
