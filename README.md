# Fleet Management - Architecture Documentation

## System Overview

Fleet Management system is a comprehensive AI-powered car rental demand prediction and fleet management platform built on AWS using Amazon Bedrock AgentCore. The system combines local tools, MCP gateway tools, and external APIs to provide intelligent fleet insights and demand forecasting.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE LAYER                                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │                                     │
         ┌──────────▼──────────┐              ┌──────────▼──────────┐
         │  React Web App      │              │   Mobile/Desktop    │
         │  (CloudFront + S3)  │              │   Future Clients    │
         │                     │              │                     │
         │  - Chat Interface   │              │                     │
         │  - Fleet Search     │              │                     │
         │  - Cognito Auth     │              │                     │
         └──────────┬──────────┘              └─────────────────────┘
                    │
                    │ HTTPS
                    │
┌───────────────────▼─────────────────────────────────────────────────────────────┐
│                           API GATEWAY LAYER                                      │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │  Amazon API Gateway (REST API)                                         │    │
│  │  - /chat endpoint (POST)                                               │    │
│  │  - CORS enabled                                                        │    │
│  │  - CloudWatch logging                                                  │    │
│  └────────────────────────────┬───────────────────────────────────────────┘    │
└─────────────────────────────────┼──────────────────────────────────────────────┘
                                  │
                                  │ Invoke
                                  │
┌─────────────────────────────────▼──────────────────────────────────────────────┐
│                        LAMBDA PROXY LAYER (VPC)                                 │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │  Runtime Proxy Lambda (runtime-proxy)                            │    │
│  │  - Python 3.12                                                         │    │
│  │  - VPC with NAT Gateway                                                │    │
│  │  - Cognito authentication                                              │    │
│  │  - IAM-based AgentCore invocation                                      │    │
│  │  - Environment: RUNTIME_ARN, COGNITO_*, API_KEYS                       │    │
│  └────────────────────────────┬───────────────────────────────────────────┘    │
└─────────────────────────────────┼──────────────────────────────────────────────┘
                                  │
                                  │ IAM Auth
                                  │
┌─────────────────────────────────▼──────────────────────────────────────────────┐
│                      AMAZON BEDROCK AGENTCORE RUNTIME                           │
│                         (Docker Container on ECS)                               │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │  Strands Agent Runtime (strands_runtime.py)                            │    │
│  │                                                                         │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │    │
│  │  │  Claude 3 Haiku Model (Bedrock)                                  │  │    │
│  │  │  - Temperature: 0.3                                              │  │    │
│  │  │  - System Prompt: Fleet management & demand prediction           │  │    │
│  │  └──────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                         │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │    │
│  │  │  LOCAL TOOLS (fleet_tools.py)                                    │  │    │
│  │  │  ┌────────────────────────────────────────────────────────────┐  │  │    │
│  │  │  │ 1. search_vehicles_general()                               │  │  │    │
│  │  │  │    - Search by make/model/category nationwide              │  │  │    │
│  │  │  │    - DynamoDB scan with filters                            │  │  │    │
│  │  │  │                                                             │  │  │    │
│  │  │  │ 2. search_fleet_by_zip()                                   │  │  │    │
│  │  │  │    - Search by specific ZIP code                           │  │  │    │
│  │  │  │    - DynamoDB GSI query (zip_code-index)                   │  │  │    │
│  │  │  │                                                             │  │  │    │
│  │  │  │ 3. get_fleet_summary()                                     │  │  │    │
│  │  │  │    - Fleet statistics by location                          │  │  │    │
│  │  │  │    - Availability, categories, pricing                     │  │  │    │
│  │  │  │                                                             │  │  │    │
│  │  │  │ 4. get_national_holidays()                                 │  │  │    │
│  │  │  │    - U.S. holidays via Nager.Date API                      │  │  │    │
│  │  │  │    - Demand prediction (holidays = peak demand)            │  │  │    │
│  │  │  │                                                             │  │  │    │
│  │  │  │ 5. get_local_events()                                      │  │  │    │
│  │  │  │    - Concerts, sports, festivals via Ticketmaster API      │  │  │    │
│  │  │  │    - Event-driven demand spikes                            │  │  │    │
│  │  │  └────────────────────────────────────────────────────────────┘  │  │    │
│  │  └──────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                         │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │    │
│  │  │  MCP CLIENT (MCPClient)                                          │  │    │
│  │  │  - Connects to AgentCore Gateway                                 │  │    │
│  │  │  - JWT token authentication                                      │  │    │
│  │  │  - Streamable HTTP transport                                     │  │    │
│  │  └────────────────────┬─────────────────────────────────────────────┘  │    │
│  └───────────────────────┼────────────────────────────────────────────────┘    │
└────────────────────────────┼───────────────────────────────────────────────────┘
                             │
                             │ HTTPS + JWT
                             │
┌────────────────────────────▼───────────────────────────────────────────────────┐
│                    AMAZON BEDROCK AGENTCORE GATEWAY                             │
│                         (Managed MCP Gateway)                                   │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │  Gateway Configuration                                                 │    │
│  │  - Gateway ID: mcp-gateway-*                                     │    │
│  │  - Authentication: Cognito JWT                                         │    │
│  │  - Targets: Weather + Flight                                           │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────┐        │
│  │  Weather Target             │    │  Flight Target                  │        │
│  │  - Lambda: weather_lambda   │    │  - Lambda: flight_lambda        │        │
│  │  - Tool: get_weather_forecast│   │  - Tool: get_flight_traffic     │        │
│  └─────────────┬───────────────┘    └─────────────┬───────────────────┘        │
└────────────────┼──────────────────────────────────┼────────────────────────────┘
                 │                                   │
                 │ Invoke                            │ Invoke
                 │                                   │
┌────────────────▼───────────────┐  ┌───────────────▼────────────────────────────┐
│  Weather Lambda                │  │  Flight Lambda                             │
│  (weather-forecast)               │  │     (flight-traffic)                    │
│                                │  │                                            │
│  - Open-Meteo API              │  │  - AviationStack API                       │
│  - Geocoding + Forecast        │  │  - Airport arrivals/departures             │
│  - 7-16 day forecasts          │  │  - Flight status tracking                  │
│  - Temp, precipitation, codes  │  │  - Demand prediction near airports         │
└────────────────────────────────┘  └────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                          │
└─────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│  DynamoDB Table: -fleet-inventory                                         │
│                                                                                │
│  Partition Key: vehicle_id (STRING)                                            │
│                                                                                │
│  Attributes:                                                                   │
│  - vehicle_id, make, model, year, category                                     │
│  - status (available/rented/maintenance)                                       │
│  - location, zip_code, daily_rate                                              │
│                                                                                │
│  Global Secondary Indexes:                                                     │
│  1. zip_code-index                                                             │
│     - Partition: zip_code                                                      │
│     - Sort: status                                                             │
│                                                                                │
│  2. location-index                                                             │
│     - Partition: location                                                      │
│                                                                                │
│  Data: ~1,855 vehicles across 10 major U.S. cities                             │
└────────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION & AUTHORIZATION                           │
└─────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│  Amazon Cognito User Pool                                                      │
│  - User Pool ID: us-east-1_*                                                   │
│  - Client ID: *                                                                │
│  - Authentication: Username/Password, SRP                                      │
│  - Token Validity: 1 hour (access/id), 30 days (refresh)                      │
│  - Test User: test-user / TestPass123!                                         │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│  Amazon Cognito Identity Pool                                                  │
│  - Federated identity for React app                                            │
│  - Authenticated role with:                                                    │
│    * DynamoDB read access (fleet data)                                         │
│    * AgentCore Runtime invocation                                              │
└────────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL APIS & SERVICES                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────────┐
│  Open-Meteo API      │  │  Nager.Date API      │  │  Ticketmaster API        │
│  (Weather)           │  │  (Holidays)          │  │  (Events)                │
│                      │  │                      │  │                          │
│  - Free, no key      │  │  - Free, no key      │  │  - API key required      │
│  - Geocoding         │  │  - U.S. holidays     │  │  - Concert/sports data   │
│  - 16-day forecasts  │  │  - Date filtering    │  │  - Venue information     │
└──────────────────────┘  └──────────────────────┘  └──────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  AviationStack API                                                           │
│  (Flight Traffic)                                                            │
│                                                                              │
│  - API key required                                                          │
│  - Real-time flight data                                                     │
│  - Airport arrivals/departures                                               │
│  - Flight status tracking                                                    │
└──────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────┐
│                         IAM ROLES & PERMISSIONS                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│  LambdaExecutionRole                                                      │
│  - Used by: weather_lambda, flight_lambda                                      │
│  - Permissions: Lambda basic execution, DynamoDB read/write                    │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│  GatewayExecutionRole                                                     │
│  - Used by: AgentCore Gateway                                                  │
│  - Permissions: Lambda invoke (weather + flight functions)                     │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│  StrandsAgentCoreRuntimeRole                                              │
│  - Used by: AgentCore Runtime (Docker container)                               │
│  - Permissions:                                                                │
│    * Bedrock full access (Claude model)                                        │
│    * CloudWatch logs                                                           │
│    * SSM read-only (config parameters)                                         │
│    * ECR read-only (Docker images)                                             │
│    * DynamoDB read-only (fleet data)                                           │
│    * AgentCore Gateway invocation                                              │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│  RuntimeProxyLambdaRole                                                   │
│  - Used by: runtime_proxy_lambda                                               │
│  - Permissions:                                                                │
│    * Lambda basic + VPC execution                                              │
│    * DynamoDB read-only                                                        │
│    * SSM read-only                                                             │
│    * Cognito admin auth                                                        │
│    * AgentCore Runtime invocation                                              │
└────────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CONFIGURATION STORAGE                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│  AWS Systems Manager Parameter Store                                          │
│                                                                                │
│  //agentcore/weather_gateway_id                                           │
│  //agentcore/weather_gateway_url                                          │
│  //agentcore/weather_gateway_arn                                          │
│  //agentcore/gateway_id                                                   │
│  //agentcore/strands_runtime_arn                                          │
│  //agentcore/api_gateway_url                                              │
│  //agentcore/cognito_user_pool_id                                         │
│  //agentcore/cognito_client_id                                            │
│  //agentcore/cognito_issuer                                               │
│  //agentcore/cognito_identity_pool_id                                     │
│  //agentcore/weather_lambda_arn                                           │
│  //agentcore/flight_lambda_arn                                            │
│  //agentcore/test_access_token                                            │
└────────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────┐
│                         MONITORING & LOGGING                                     │
└─────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│  Amazon CloudWatch                                                             │
│                                                                                │
│  Log Groups:                                                                   │
│  - /aws/lambda/-runtime-proxy                                             │
│  - /aws/lambda/-weather-forecast                                          │
│  - /aws/lambda/-flight-traffic                                            │
│  - /aws/bedrock-agentcore/runtimes/_strands_runtime-*/DEFAULT             │
│  - /aws/bedrock-agentcore/runtimes/_strands_runtime-*/runtime-logs        │
│  - /aws/apigateway/-runtime-proxy-api                                     │
│                                                                                │
│  Metrics:                                                                      │
│  - Lambda invocations, duration, errors                                        │
│  - API Gateway requests, latency, 4xx/5xx                                      │
│  - DynamoDB read/write capacity, throttles                                     │
└────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. User Chat Request Flow
```
User → React App → API Gateway → Runtime Proxy Lambda → AgentCore Runtime
                                                              ↓
                                                    ┌─────────┴─────────┐
                                                    │                   │
                                              Local Tools         MCP Gateway
                                                    │                   │
                                              DynamoDB          Weather/Flight
                                              External APIs        Lambdas
```

### 2. Tool Invocation Flow

#### Local Tools (Direct)
```
Runtime → fleet_tools.py → DynamoDB/External APIs → Response → Runtime → User
```

#### MCP Tools (Gateway)
```
Runtime → MCP Client → AgentCore Gateway → Lambda (Weather/Flight) → External API
                                                                            ↓
Runtime ← Response ← Gateway ← Lambda ← API Response
```

## Key Components

### Frontend (React)
- **Location**: `frontend/react-app/`
- **Hosting**: CloudFront + S3
- **Features**:
  - Chat interface with AI agent
  - Fleet search functionality
  - Cognito authentication
  - Real-time responses

### Backend Services

#### 1. API Gateway + Lambda Proxy
- **Purpose**: Bridge React app to AgentCore Runtime
- **Components**:
  - API Gateway REST API
  - Lambda function in VPC with NAT Gateway
  - Cognito authentication
  - IAM-based runtime invocation

#### 2. AgentCore Runtime (Docker)
- **Purpose**: Main AI agent orchestration
- **Components**:
  - Strands Agent framework
  - Claude 3 Haiku model
  - Local tools (5 functions)
  - MCP client for gateway tools
  - Deployed on ECS via ECR

#### 3. AgentCore Gateway
- **Purpose**: MCP tool provider
- **Components**:
  - Weather forecast tool (Lambda)
  - Flight traffic tool (Lambda)
  - JWT authentication
  - Lambda invocation

#### 4. Lambda Functions
- **runtime_proxy_lambda**: API Gateway → Runtime proxy
- **weather_lambda**: Weather forecasts via Open-Meteo
- **flight_lambda**: Flight data via AviationStack

### Data Storage

#### DynamoDB Table
- **Name**: -fleet-inventory
- **Records**: ~1,855 vehicles
- **Locations**: 10 major U.S. cities
- **Indexes**: 
  - Primary: vehicle_id
  - GSI: zip_code-index (for location queries)
  - GSI: location-index (for city queries)

### Authentication

#### Cognito User Pool
- Username/password authentication
- JWT token generation
- Test user: test-user / TestPass123!

#### Cognito Identity Pool
- Federated identity for React app
- AWS SDK credential provider
- Scoped IAM permissions

## Tool Capabilities

### Local Tools (5)
1. **search_vehicles_general**: Nationwide vehicle search by make/model/category
2. **search_fleet_by_zip**: Location-specific vehicle search
3. **get_fleet_summary**: Fleet statistics and availability
4. **get_national_holidays**: U.S. holiday calendar for demand prediction
5. **get_local_events**: Concerts, sports, festivals via Ticketmaster

### MCP Gateway Tools (2)
1. **get_weather_forecast**: Weather data for demand prediction
2. **get_flight_traffic**: Airport activity for rental demand analysis

## Deployment

### Infrastructure as Code
- **CDK Stacks**:
  - McpStack: Lambda functions, DynamoDB, Cognito, IAM
  - ApiGatewayStack: API Gateway, Runtime Proxy Lambda, VPC
  - FrontendStack: CloudFront, S3

### Deployment Scripts
- **deploy_all.sh**: Complete deployment automation
  1. Deploy backend CDK stacks
  2. Deploy AgentCore Gateway (boto3)
  3. Load fleet data to DynamoDB
  4. Deploy AgentCore Runtime (Docker)
  5. Update environment files
  6. Build and deploy React frontend

- **destroy_all.sh**: Complete teardown
  1. Destroy frontend stack
  2. Delete AgentCore Runtime
  3. Delete AgentCore Gateway
  4. Destroy backend stacks
  5. Clean up SSM parameters

## Security

### Network Security
- VPC with private subnets for Lambda
- NAT Gateway for outbound internet access
- Security groups for Lambda functions
- CloudFront for HTTPS termination

### Authentication & Authorization
- Cognito JWT tokens for user authentication
- IAM roles with least-privilege permissions
- SigV4 signing for AWS service calls
- API key management via environment variables

### Data Protection
- S3 bucket with private access only
- DynamoDB encryption at rest
- CloudWatch logs for audit trail
- SSM Parameter Store for secrets

## Scalability

### Auto-Scaling Components
- Lambda functions (automatic)
- DynamoDB (on-demand billing)
- CloudFront (global CDN)
- AgentCore Runtime (ECS auto-scaling)

### Performance Optimizations
- DynamoDB GSI for fast queries
- CloudFront caching
- Lambda memory optimization (256-512 MB)
- VPC endpoint for AgentCore (future)

## Cost Optimization

### Pay-Per-Use Services
- Lambda (per invocation)
- DynamoDB (on-demand)
- API Gateway (per request)
- Bedrock (per token)

### Fixed Costs
- NAT Gateway (~$32/month)
- CloudFront (minimal with free tier)
- S3 storage (minimal)

## Future Enhancements

1. **VPC Endpoint for AgentCore**: Eliminate NAT Gateway cost
2. **Additional MCP Tools**: 
   - Traffic data
   - Hotel occupancy
   - Gas prices
3. **Real-time Fleet Updates**: DynamoDB Streams + Lambda
4. **Advanced Analytics**: QuickSight dashboards
5. **Multi-region Deployment**: Global availability
6. **Mobile Apps**: iOS/Android native apps
7. **Voice Interface**: Alexa/Google Assistant integration

## Technology Stack

### Frontend
- React 19.2.0
- AWS Amplify (Cognito integration)
- Axios (HTTP client)

### Backend
- Python 3.12
- AWS CDK (Infrastructure)
- Boto3 (AWS SDK)
- Strands Agent Framework
- MCP (Model Context Protocol)

### AI/ML
- Amazon Bedrock (Claude 3 Haiku)
- Bedrock AgentCore (Runtime + Gateway)

### AWS Services
- Lambda, API Gateway, DynamoDB
- Cognito, IAM, SSM
- CloudFront, S3, CloudWatch
- ECR, ECS (for Docker runtime)
- VPC, NAT Gateway

### External APIs
- Open-Meteo (Weather)
- Nager.Date (Holidays)
- Ticketmaster (Events)
- AviationStack (Flights)

## Monitoring & Observability

### CloudWatch Logs
- All Lambda functions
- AgentCore Runtime logs
- API Gateway access logs

### CloudWatch Metrics
- Lambda performance metrics
- API Gateway request metrics
- DynamoDB capacity metrics
- Custom application metrics

### Debugging
- X-Ray tracing (optional)
- CloudWatch Insights queries
- Lambda function logs
- Runtime container logs

## Development Workflow

1. **Local Development**: Test tools locally with mock data
2. **CDK Deployment**: Deploy infrastructure changes
3. **Runtime Update**: Rebuild and redeploy Docker container
4. **Frontend Build**: Build React app and upload to S3
5. **Testing**: Use test credentials to validate
6. **Monitoring**: Check CloudWatch logs and metrics

## Conclusion

The  MCP Fleet Management system demonstrates a modern, serverless, AI-powered architecture that combines:
- **Scalability**: Auto-scaling AWS services
- **Intelligence**: Claude 3 Haiku with custom tools
- **Flexibility**: MCP protocol for extensible tools
- **Security**: Multi-layer authentication and authorization
- **Cost-Efficiency**: Pay-per-use pricing model
- **Maintainability**: Infrastructure as Code with CDK

The architecture is production-ready and can be extended with additional features, tools, and integrations as needed.
