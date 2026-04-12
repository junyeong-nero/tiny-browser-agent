import React from 'react';
import ReactDOM from 'react-dom/client';
import { ArtifactClientProvider } from './api/ArtifactClientContext';
import { bootstrapDesktopBridge } from './api/bootstrapDesktopBridge';
import { SessionClientProvider } from './api/SessionClientContext';
import App from './App';

bootstrapDesktopBridge();

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <ArtifactClientProvider>
      <SessionClientProvider>
        <App />
      </SessionClientProvider>
    </ArtifactClientProvider>
  </React.StrictMode>
);
