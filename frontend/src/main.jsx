import React from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider } from 'goflow-core';
import 'goflow-core/styles.css';
import App from './App';
import { AuthProvider } from './auth';
import './styles/corporate.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider>
      <AuthProvider apiBase="/api">
        <App />
      </AuthProvider>
    </ThemeProvider>
  </React.StrictMode>
);
