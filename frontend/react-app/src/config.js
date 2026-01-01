export const config = {
  runtimeEndpoint: process.env.REACT_APP_RUNTIME_ENDPOINT || '',
  cognito: {
    region: process.env.REACT_APP_AWS_REGION || 'us-east-1',
    userPoolId: process.env.REACT_APP_COGNITO_USER_POOL_ID || '',
    userPoolClientId: process.env.REACT_APP_COGNITO_CLIENT_ID || '',
    identityPoolId: process.env.REACT_APP_COGNITO_IDENTITY_POOL_ID || 'us-east-1:6192ca5e-b6e3-4c22-9b94-2485b0b83550',
  },
  dynamoDBTable: 'hertz-fleet-inventory',
  region: process.env.REACT_APP_AWS_REGION || 'us-east-1',
  runtimeId: 'hertz_strands_runtime-JUlxGW9FAs',
};
