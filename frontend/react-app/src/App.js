import React, { useState } from 'react';
import { Amplify } from 'aws-amplify';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import '@cloudscape-design/global-styles/index.css';
import {
  AppLayout,
  TopNavigation,
  SideNavigation,
  ContentLayout,
} from '@cloudscape-design/components';
import FleetSearch from './components/FleetSearch';
import ChatInterface from './components/ChatInterface';
import { config } from './config';

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: config.cognito.userPoolId,
      userPoolClientId: config.cognito.userPoolClientId,
    },
  },
});

function App() {
  const [activeHref, setActiveHref] = useState('/chat');
  const [navigationOpen, setNavigationOpen] = useState(true);

  const navItems = [
    { 
      type: 'link', 
      text: '💬 Chat Assistant', 
      href: '/chat'
    },
    { 
      type: 'link', 
      text: '🔍 Fleet Search', 
      href: '/fleet'
    },
  ];

  const renderContent = () => {
    switch (activeHref) {
      case '/chat':
        return <ChatInterface />;
      case '/fleet':
      default:
        return <FleetSearch />;
    }
  };

  return (
    <Authenticator>
      {({ signOut, user }) => (
        <>
          <TopNavigation
            identity={{
              href: '/',
              title: '🚗 Hertz Fleet Management'
            }}
            utilities={[
              {
                type: 'button',
                text: user?.username || 'User',
                description: user?.attributes?.email,
                iconName: 'user-profile',
              },
              {
                type: 'button',
                text: 'Sign out',
                iconName: 'unlocked',
                onClick: signOut,
              },
            ]}
          />
          <AppLayout
            navigation={
              <SideNavigation
                activeHref={activeHref}
                onFollow={(event) => {
                  event.preventDefault();
                  setActiveHref(event.detail.href);
                }}
                items={navItems}
              />
            }
            navigationOpen={navigationOpen}
            onNavigationChange={({ detail }) => setNavigationOpen(detail.open)}
            content={
              <ContentLayout>
                {renderContent()}
              </ContentLayout>
            }
            toolsHide
          />
        </>
      )}
    </Authenticator>
  );
}

export default App;
