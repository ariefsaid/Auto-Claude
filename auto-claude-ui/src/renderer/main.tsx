// Initialize browser mock before anything else (no-op in Electron)
import { browserMockReady } from './lib/browser-mock';

import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './styles/globals.css';

// Wait for browser mock initialization before rendering
// This ensures window.electronAPI is properly set up (HTTP client or mocks)
browserMockReady.then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
});
