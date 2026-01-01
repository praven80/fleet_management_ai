import React, { useState, useRef, useEffect } from 'react';
import {
  Header,
  Box,
  Input,
  Button,
  Spinner,
} from '@cloudscape-design/components';
import { sendChatMessage } from '../services/api';

const ChatInterface = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const currentInput = input.trim();
    setInput('');
    setLoading(true);

    try {
      const response = await sendChatMessage(currentInput);
      
      // Extract text from response
      let responseText = '';
      if (typeof response === 'string') {
        responseText = response;
      } else if (response && response.response) {
        responseText = response.response;
      } else if (response && response.vehicles) {
        // If it's a vehicle search response, format it nicely
        responseText = response.response || 'Found vehicles in the fleet.';
      } else {
        responseText = JSON.stringify(response, null, 2);
      }
      
      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: responseText,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${error.message || 'Failed to get response. Please check your connection and try again.'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    // Native DOM event handler for Enter key
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: 'calc(100vh - 48px)', // Account for top navigation
      width: '100%',
    }}>
      {/* Header */}
      <div style={{ 
        padding: '20px',
        backgroundColor: '#ffffff',
        borderBottom: '2px solid #FFC107',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
      }}>
        <Header 
          variant="h1" 
          description="Chat with the Hertz AI assistant for fleet insights and demand predictions"
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '12px', whiteSpace: 'nowrap' }}>
            <span style={{ fontSize: '32px' }}>🚗</span>
            <span>Fleet Assistant</span>
          </span>
        </Header>
      </div>

      {/* Messages Area - Scrollable */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px',
          backgroundColor: '#fafafa',
        }}
      >
        {messages.length === 0 && !loading && (
          <Box textAlign="center" color="text-body-secondary" padding="xxl">
            <Box variant="h2" padding={{ bottom: 's' }}>
              Welcome to Hertz Fleet Assistant
            </Box>
            <Box variant="p" color="text-body-secondary">
              Ask me about fleet availability, demand predictions, weather, events, and more!
            </Box>
          </Box>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            style={{
              display: 'flex',
              justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
              marginBottom: '16px',
              gap: '12px',
              alignItems: 'flex-start',
            }}
          >
            {message.role === 'assistant' && (
              <div
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  backgroundColor: '#FFC107',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '20px',
                  flexShrink: 0,
                  boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                }}
              >
                🚗
              </div>
            )}
            <div
              style={{
                maxWidth: '70%',
                padding: '12px 16px',
                borderRadius: '12px',
                backgroundColor: message.role === 'user' ? '#0972d3' : '#ffffff',
                color: message.role === 'user' ? '#ffffff' : '#000000',
                boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
              }}
            >
              <div style={{ fontSize: '14px', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
                {message.content}
              </div>
              {message.role === 'assistant' && (
                <div
                  style={{
                    fontSize: '11px',
                    marginTop: '6px',
                    opacity: 0.7,
                  }}
                >
                  {message.timestamp.toLocaleTimeString()}
                </div>
              )}
            </div>
            {message.role === 'user' && (
              <div
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '20px',
                  color: '#ffffff',
                  flexShrink: 0,
                  boxShadow: '0 2px 8px rgba(102, 126, 234, 0.4)',
                }}
              >
                👨‍💼
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: '16px' }}>
            <div
              style={{
                padding: '12px 16px',
                borderRadius: '12px',
                backgroundColor: '#ffffff',
                boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
              }}
            >
              <Spinner size="normal" /> <span style={{ marginLeft: '8px' }}>Thinking...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area - Fixed at Bottom */}
      <div
        style={{
          padding: '16px 20px',
          backgroundColor: '#ffffff',
          borderTop: '2px solid #e9ebed',
          boxShadow: '0 -2px 8px rgba(0,0,0,0.1)',
        }}
      >
        <div style={{ 
          display: 'flex', 
          gap: '12px', 
          alignItems: 'center',
          width: '100%',
        }}>
          <div style={{ flex: 1 }} onKeyDown={handleKeyDown}>
            <Input
              value={input}
              onChange={({ detail }) => setInput(detail.value)}
              placeholder="Type your message and press Enter..."
              disabled={loading}
              autoFocus
            />
          </div>
          <Button
            variant="primary"
            onClick={handleSend}
            disabled={loading || !input.trim()}
            iconName="send"
          >
            Send
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
