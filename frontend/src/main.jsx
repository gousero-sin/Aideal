import React from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider } from 'goflow-core';
import 'goflow-core/styles.css';
import App from './App';
import './styles/corporate.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
