"""
CDK Stack for Hertz MCP Tools Infrastructure
Creates Lambda functions, IAM roles, and AgentCore Gateway resources for:
- Weather forecasting
- Flight traffic monitoring
- Future tools...
"""
from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    RemovalPolicy,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_bedrockagentcore as agentcore,
    aws_cognito as cognito,
    aws_dynamodb as dynamodb,
)
from constructs import Construct
import json
import os


class HertzMcpStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ========================================================================
        # DynamoDB Table for Fleet Data
        # ========================================================================
        fleet_table = dynamodb.Table(
            self,
            "FleetInventoryTable",
            table_name="hertz-fleet-inventory",
            partition_key=dynamodb.Attribute(
                name="vehicle_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True,
        )
        
        # Add GSI for querying by zip code
        fleet_table.add_global_secondary_index(
            index_name="zip_code-index",
            partition_key=dynamodb.Attribute(
                name="zip_code",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
        )
        
        # Add GSI for querying by location
        fleet_table.add_global_secondary_index(
            index_name="location-index",
            partition_key=dynamodb.Attribute(
                name="location",
                type=dynamodb.AttributeType.STRING
            ),
        )

        # ========================================================================
        # Lambda Execution Role (shared by both functions)
        # ========================================================================
        lambda_role = iam.Role(
            self,
            "WeatherLambdaRole",
            role_name="HertzLambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Hertz Lambda functions",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        
        # Grant DynamoDB access to Lambda role
        fleet_table.grant_read_write_data(lambda_role)

        # ========================================================================
        # Lambda Functions
        # ========================================================================
        
        # Weather Lambda
        weather_lambda = lambda_.Function(
            self,
            "WeatherForecastFunction",
            function_name="hertz-weather-forecast",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="weather_lambda.lambda_handler",
            code=lambda_.Code.from_asset("../lambda"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            description="Weather forecast tool for AgentCore Gateway",
            environment={
                "LOG_LEVEL": "INFO"
            }
        )
        
        # Flight Traffic Lambda
        flight_lambda = lambda_.Function(
            self,
            "FlightTrafficFunction",
            function_name="hertz-flight-traffic",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="flight_lambda.lambda_handler",
            code=lambda_.Code.from_asset("../lambda"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            description="Flight traffic tool for AgentCore Gateway",
            environment={
                "LOG_LEVEL": "INFO",
                "AVIATIONSTACK_API_KEY": os.environ.get("AVIATIONSTACK_API_KEY", "")
            }
        )

        # ========================================================================
        # Gateway Execution Role
        # ========================================================================
        gateway_role = iam.Role(
            self,
            "GatewayExecutionRole",
            role_name="HertzGatewayExecutionRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Execution role for Hertz AgentCore Gateway",
        )

        # Add Lambda invoke permissions to gateway role (both functions)
        gateway_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[
                    weather_lambda.function_arn,
                    flight_lambda.function_arn
                ],
            )
        )

        # ========================================================================
        # Runtime Execution Role (for AgentCore Runtime)
        # ========================================================================
        runtime_role = iam.Role(
            self,
            "StrandsRuntimeExecutionRole",
            role_name="HertzStrandsAgentCoreRuntimeRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Execution role for Hertz Strands AgentCore Runtime",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMReadOnlyAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonDynamoDBReadOnlyAccess"),
            ],
        )
        
        # Grant DynamoDB read access to runtime role
        fleet_table.grant_read_data(runtime_role)
        
        # Add Gateway access policy
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeGateway",
                    "bedrock-agentcore:GetGateway",
                    "bedrock-agentcore:ListGateways",
                ],
                resources=["*"],
            )
        )

        # ========================================================================
        # Cognito User Pool for Gateway Authentication
        # ========================================================================
        
        user_pool = cognito.UserPool(
            self,
            "HertzGatewayUserPool",
            user_pool_name="hertz-mcp-gateway-users",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True, email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True)
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        
        # Create user pool client
        user_pool_client = cognito.UserPoolClient(
            self,
            "HertzGatewayUserPoolClient",
            user_pool=user_pool,
            user_pool_client_name="hertz-mcp-gateway-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                admin_user_password=True,
                user_srp=True,  # Enable SRP authentication for Amplify
            ),
            generate_secret=False,
            refresh_token_validity=Duration.days(30),
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
        )
        
        # Store Cognito configuration in SSM
        ssm.StringParameter(
            self,
            "CognitoUserPoolIdParameter",
            parameter_name="/hertz/agentcore/cognito_user_pool_id",
            string_value=user_pool.user_pool_id,
            description="Cognito User Pool ID for gateway authentication",
        )
        
        ssm.StringParameter(
            self,
            "CognitoClientIdParameter",
            parameter_name="/hertz/agentcore/cognito_client_id",
            string_value=user_pool_client.user_pool_client_id,
            description="Cognito Client ID for gateway authentication",
        )
        
        ssm.StringParameter(
            self,
            "CognitoIssuerParameter",
            parameter_name="/hertz/agentcore/cognito_issuer",
            string_value=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}",
            description="Cognito issuer URL for JWT validation",
        )
        
        # ========================================================================
        # Cognito Identity Pool for React App AWS SDK Access
        # ========================================================================
        
        identity_pool = cognito.CfnIdentityPool(
            self,
            "HertzIdentityPool",
            identity_pool_name="hertz-react-identity-pool",
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=user_pool_client.user_pool_client_id,
                    provider_name=user_pool.user_pool_provider_name,
                )
            ],
        )
        
        # IAM role for authenticated users
        authenticated_role = iam.Role(
            self,
            "CognitoAuthenticatedRole",
            assumed_by=iam.FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                {
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    },
                },
                "sts:AssumeRoleWithWebIdentity",
            ),
        )
        
        # Grant permissions to invoke AgentCore Runtime
        authenticated_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:GetAgentRuntime",
                ],
                resources=[runtime_role.role_arn.replace(":role/", ":runtime/*")],
            )
        )
        
        # Grant DynamoDB read access for fleet search
        fleet_table.grant_read_data(authenticated_role)
        
        # Attach role to identity pool
        cognito.CfnIdentityPoolRoleAttachment(
            self,
            "IdentityPoolRoleAttachment",
            identity_pool_id=identity_pool.ref,
            roles={
                "authenticated": authenticated_role.role_arn,
            },
        )
        
        # Store Identity Pool ID in SSM
        ssm.StringParameter(
            self,
            "CognitoIdentityPoolIdParameter",
            parameter_name="/hertz/agentcore/cognito_identity_pool_id",
            string_value=identity_pool.ref,
            description="Cognito Identity Pool ID for React app AWS SDK access",
        )
        
        # ========================================================================
        # Note: AgentCore Gateway is created via boto3 post-deployment
        # See: deploy_gateway.py
        # This is because the CDK constructs for AgentCore are very new and
        # have validation issues. We use CDK for stable resources (Lambda, IAM)
        # and boto3 for the gateway.
        # ========================================================================

        ssm.StringParameter(
            self,
            "WeatherLambdaArnParameter",
            parameter_name="/hertz/agentcore/weather_lambda_arn",
            string_value=weather_lambda.function_arn,
            description="Lambda function ARN for weather tool",
        )
        
        ssm.StringParameter(
            self,
            "FlightLambdaArnParameter",
            parameter_name="/hertz/agentcore/flight_lambda_arn",
            string_value=flight_lambda.function_arn,
            description="Lambda function ARN for flight traffic tool",
        )

        # ========================================================================
        # Outputs
        # ========================================================================
        
        CfnOutput(
            self,
            "WeatherLambdaName",
            value=weather_lambda.function_name,
            description="Weather forecast Lambda function name",
            export_name="HertzWeatherLambdaName",
        )

        CfnOutput(
            self,
            "WeatherLambdaArn",
            value=weather_lambda.function_arn,
            description="Weather forecast Lambda function ARN",
            export_name="HertzWeatherLambdaArn",
        )
        
        CfnOutput(
            self,
            "FlightLambdaName",
            value=flight_lambda.function_name,
            description="Flight traffic Lambda function name",
            export_name="HertzFlightLambdaName",
        )

        CfnOutput(
            self,
            "FlightLambdaArn",
            value=flight_lambda.function_arn,
            description="Flight traffic Lambda function ARN",
            export_name="HertzFlightLambdaArn",
        )

        CfnOutput(
            self,
            "LambdaRoleArn",
            value=lambda_role.role_arn,
            description="Lambda execution role ARN",
            export_name="HertzLambdaRoleArn",
        )

        CfnOutput(
            self,
            "GatewayRoleArn",
            value=gateway_role.role_arn,
            description="Gateway execution role ARN (use in deploy_gateway.py)",
            export_name="HertzGatewayRoleArn",
        )
        
        CfnOutput(
            self,
            "RuntimeRoleArn",
            value=runtime_role.role_arn,
            description="Runtime execution role ARN (use in deploy_agentcore_runtime.py)",
            export_name="HertzRuntimeRoleArn",
        )
        
        CfnOutput(
            self,
            "CognitoUserPoolId",
            value=user_pool.user_pool_id,
            description="Cognito User Pool ID",
            export_name="HertzCognitoUserPoolId",
        )
        
        CfnOutput(
            self,
            "CognitoClientId",
            value=user_pool_client.user_pool_client_id,
            description="Cognito Client ID",
            export_name="HertzCognitoClientId",
        )
        
        CfnOutput(
            self,
            "CognitoIssuer",
            value=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}",
            description="Cognito Issuer URL",
            export_name="HertzCognitoIssuer",
        )
        
        CfnOutput(
            self,
            "CognitoIdentityPoolId",
            value=identity_pool.ref,
            description="Cognito Identity Pool ID for React app",
            export_name="HertzCognitoIdentityPoolId",
        )
        
        CfnOutput(
            self,
            "FleetTableName",
            value=fleet_table.table_name,
            description="DynamoDB Fleet Inventory Table Name",
            export_name="HertzFleetTableName",
        )
        
        CfnOutput(
            self,
            "FleetTableArn",
            value=fleet_table.table_arn,
            description="DynamoDB Fleet Inventory Table ARN",
            export_name="HertzFleetTableArn",
        )
