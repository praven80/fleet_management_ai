import axios from 'axios';
import { fetchAuthSession } from 'aws-amplify/auth';
import { config } from '../config';

const getAuthToken = async () => {
  try {
    const session = await fetchAuthSession();
    const token = session.tokens?.accessToken?.toString();
    if (!token) {
      throw new Error('No access token available');
    }
    return token;
  } catch (error) {
    console.error('Error getting auth token:', error);
    throw error;
  }
};

export const sendChatMessage = async (message) => {
  try {
    const token = await getAuthToken();
    
    // Call the runtime endpoint
    const response = await axios.post(
      config.runtimeEndpoint,
      { prompt: message },
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        timeout: 60000, // 60 second timeout
      }
    );
    
    // The FastAPI wrapper returns {response: "text", session_id: "..."}
    // Try to extract JSON from the response text if it contains vehicle data
    const data = response.data;
    
    if (data.response) {
      // Try to parse JSON from the response text
      try {
        const jsonMatch = data.response.match(/\{[\s\S]*"vehicles"[\s\S]*\}/);
        if (jsonMatch) {
          const parsed = JSON.parse(jsonMatch[0]);
          return { ...data, vehicles: parsed.vehicles };
        }
      } catch (e) {
        // Not JSON, return as is
      }
    }
    
    return data;
  } catch (error) {
    console.error('Error sending chat message:', error);
    if (error.response) {
      throw new Error(`Server error: ${error.response.status} - ${error.response.data?.message || error.response.statusText}`);
    } else if (error.request) {
      throw new Error('No response from server. Please check your connection.');
    } else {
      throw new Error(error.message || 'Failed to send message');
    }
  }
};

export const searchFleetVehicles = async (filters) => {
  try {
    const token = await getAuthToken();
    let prompt = 'Search for vehicles';
    const conditions = [];
    
    if (filters.make) conditions.push(`make: ${filters.make}`);
    if (filters.model) conditions.push(`model: ${filters.model}`);
    if (filters.category) conditions.push(`category: ${filters.category}`);
    if (filters.status) conditions.push(`status: ${filters.status}`);
    if (filters.zip_code) conditions.push(`in ZIP code: ${filters.zip_code}`);
    
    if (conditions.length > 0) {
      prompt += ' with ' + conditions.join(', ');
    }
    
    const response = await axios.post(
      config.runtimeEndpoint,
      { prompt },
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      }
    );
    
    const responseText = response.data;
    const jsonMatch = responseText.match(/\{[\s\S]*\}/);
    
    if (jsonMatch) {
      const data = JSON.parse(jsonMatch[0]);
      return data.vehicles || [];
    }
    
    return [];
  } catch (error) {
    console.error('Error searching fleet:', error);
    throw error;
  }
};
