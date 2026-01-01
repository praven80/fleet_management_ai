import { BedrockAgentCoreControlClient, InvokeAgentRuntimeCommand } from '@aws-sdk/client-bedrock-agentcore-control';
import { fromCognitoIdentityPool } from '@aws-sdk/credential-providers';
import { fetchAuthSession } from 'aws-amplify/auth';
import { config } from '../config';

// Runtime configuration
const RUNTIME_ID = 'hertz_strands_runtime-JUlxGW9FAs';
const ENDPOINT_NAME = 'DEFAULT';

/**
 * Get AWS credentials from Cognito
 */
const getAwsCredentials = async () => {
  try {
    const session = await fetchAuthSession();
    const idToken = session.tokens.idToken.toString();
    
    // Create credentials from Cognito Identity Pool
    // Note: You'll need to create an Identity Pool and configure it
    const credentials = fromCognitoIdentityPool({
      clientConfig: { region: config.region },
      identityPoolId: config.cognito.identityPoolId, // You'll need to add this
      logins: {
        [`cognito-idp.${config.region}.amazonaws.com/${config.cognito.userPoolId}`]: idToken,
      },
    });
    
    return credentials;
  } catch (error) {
    console.error('Error getting AWS credentials:', error);
    throw error;
  }
};

/**
 * Invoke AgentCore Runtime directly using AWS SDK
 */
export const invokeAgentRuntime = async (prompt) => {
  try {
    // Get credentials
    const credentials = await getAwsCredentials();
    
    // Create client
    const client = new BedrockAgentCoreControlClient({
      region: config.region,
      credentials,
    });
    
    // Prepare command
    const command = new InvokeAgentRuntimeCommand({
      agentRuntimeId: RUNTIME_ID,
      endpointName: ENDPOINT_NAME,
      inputText: JSON.stringify({ prompt }),
    });
    
    // Invoke runtime
    const response = await client.send(command);
    
    // Parse response
    if (response.outputText) {
      return response.outputText;
    } else if (response.body) {
      // Handle streaming response
      const decoder = new TextDecoder();
      return decoder.decode(response.body);
    } else {
      return JSON.stringify(response);
    }
  } catch (error) {
    console.error('Error invoking runtime:', error);
    throw error;
  }
};

/**
 * Send chat message to AgentCore Runtime
 */
export const sendChatMessage = async (message) => {
  try {
    const response = await invokeAgentRuntime(message);
    
    // Clean up response
    let responseText = response.trim();
    if ((responseText.startsWith('"') && responseText.endsWith('"')) ||
        (responseText.startsWith("'") && responseText.endsWith("'"))) {
      responseText = responseText.slice(1, -1);
    }
    responseText = responseText.replace(/\\n/g, '\n');
    
    return { response: responseText };
  } catch (error) {
    console.error('Error sending chat message:', error);
    throw new Error(error.message || 'Failed to send message');
  }
};
