"""
CDK Stack for API Gateway + Lambda Runtime Proxy
Enables React app to call AgentCore Runtime with full MCP tools support
Uses VPC endpoint for bedrock-agentcore-runtime (no NAT Gateway needed)
"""
from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    BundlingOptions,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_ec2 as ec2,
)
from constructs import Construct
import os


class ApiGatewayStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get configuration from CloudFormation exports (set by HertzMcpStack)
        from aws_cdk import Fn
        cognito_user_pool_id = Fn.import_value("HertzCognitoUserPoolId")
        cognito_client_id = Fn.import_value("HertzCognitoClientId")
        
        # Runtime ARN will be set after runtime deployment, use SSM for this
        runtime_arn = ssm.StringParameter.value_from_lookup(
            self, "/hertz/agentcore/strands_runtime_arn"
        )

        # Lambda execution role
        lambda_role = iam.Role(
            self,
            "RuntimeProxyLambdaRole",
            role_name="HertzRuntimeProxyLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonDynamoDBReadOnlyAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMReadOnlyAccess"
                ),
            ],
        )

        # Add permissions for Cognito and AgentCore
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:AdminInitiateAuth",
                    "cognito-idp:DescribeUserPoolClient",
                ],
                resources=[f"arn:aws:cognito-idp:{self.region}:{self.account}:userpool/*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:GetAgentRuntime",
                    "bedrock-agentcore-control:InvokeAgentRuntime",
                    "bedrock-agentcore-control:GetAgentRuntime",
                ],
                resources=["*"],
            )
        )

        # Add VPC permissions for Lambda
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaVPCAccessExecutionRole"
            )
        )

        # Create VPC for Lambda with NAT Gateway for internet access
        vpc = ec2.Vpc(
            self,
            "LambdaVpc",
            max_azs=2,
            nat_gateways=1,  # NAT Gateway for Lambda to access AgentCore Runtime
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ]
        )

        # Security group for Lambda
        lambda_sg = ec2.SecurityGroup(
            self,
            "LambdaSecurityGroup",
            vpc=vpc,
            description="Security group for Lambda runtime proxy",
            allow_all_outbound=True
        )

        # Lambda function with VPC configuration
        runtime_proxy_lambda = lambda_.Function(
            self,
            "RuntimeProxyFunction",
            function_name="hertz-runtime-proxy",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="runtime_proxy_lambda.lambda_handler",
            code=lambda_.Code.from_asset(
                "../lambda",
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ],
                )
            ),
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=512,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[lambda_sg],
            environment={
                "COGNITO_USER_POOL_ID": cognito_user_pool_id,
                "COGNITO_CLIENT_ID": cognito_client_id,
                "COGNITO_TEST_USERNAME": os.getenv("COGNITO_TEST_USERNAME", "test-user"),
                "COGNITO_TEST_PASSWORD": os.getenv("COGNITO_TEST_PASSWORD", "TestPass123!"),
                "STRANDS_RUNTIME_ARN": runtime_arn,
                "TICKETMASTER_API_KEY": os.getenv("TICKETMASTER_API_KEY", ""),
                "AVIATIONSTACK_API_KEY": os.getenv("AVIATIONSTACK_API_KEY", ""),
            },
        )

        # API Gateway
        api = apigw.RestApi(
            self,
            "RuntimeProxyApi",
            rest_api_name="hertz-runtime-proxy-api",
            description="API Gateway for React app to invoke AgentCore Runtime",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )

        # Add /chat endpoint
        chat_resource = api.root.add_resource("chat")
        chat_integration = apigw.LambdaIntegration(runtime_proxy_lambda)
        chat_resource.add_method("POST", chat_integration)

        # Store API URL in SSM
        ssm.StringParameter(
            self,
            "ApiGatewayUrlParameter",
            parameter_name="/hertz/agentcore/api_gateway_url",
            string_value=api.url,
            description="API Gateway URL for React app",
        )

        # Outputs
        CfnOutput(
            self,
            "ApiGatewayUrl",
            value=api.url,
            description="API Gateway URL",
            export_name="HertzApiGatewayUrl",
        )

        CfnOutput(
            self,
            "ChatEndpoint",
            value=f"{api.url}chat",
            description="Chat endpoint URL for React app",
            export_name="HertzChatEndpoint",
        )

        CfnOutput(
            self,
            "LambdaFunctionName",
            value=runtime_proxy_lambda.function_name,
            description="Runtime proxy Lambda function name",
            export_name="HertzRuntimeProxyLambda",
        )
