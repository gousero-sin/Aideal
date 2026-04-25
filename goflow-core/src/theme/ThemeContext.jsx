import React, { createContext, useContext, useState } from 'react';

// ============================================
// 2. THEME SYSTEM - Paleta Aquática
// ============================================

const ThemeContext = createContext(null);

export const aquaticPalette = {
    light: {
        depths: {
            surface: { bg: '#f0f9ff', text: '#0c4a6e', border: '#bae6fd' },
            shallow: { bg: '#e0f2fe', text: '#075985', border: '#7dd3fc' },
            deep: { bg: '#0ea5e9', text: '#f0f9ff', border: '#0284c7' },
            abyss: { bg: '#0c4a6e', text: '#e0f2fe', border: '#075985' }
        },
        flowStates: {
            laminar: { accent: '#22c55e', glow: 'rgba(34, 197, 94, 0.3)' },
            turbulent: { accent: '#f59e0b', glow: 'rgba(245, 158, 11, 0.3)' },
            stagnant: { accent: '#64748b', glow: 'rgba(100, 116, 139, 0.2)' }
        },
        gradient: 'linear-gradient(180deg, #f0f9ff 0%, #e0f2fe 50%, #bae6fd 100%)'
    },
    dark: {
        depths: {
            surface: { bg: '#1e3a5f', text: '#e0f2fe', border: '#2563eb' },
            shallow: { bg: '#172554', text: '#bae6fd', border: '#1d4ed8' },
            deep: { bg: '#0f172a', text: '#7dd3fc', border: '#1e40af' },
            abyss: { bg: '#020617', text: '#38bdf8', border: '#1e3a8a' }
        },
        flowStates: {
            laminar: { accent: '#4ade80', glow: 'rgba(74, 222, 128, 0.3)' },
            turbulent: { accent: '#fbbf24', glow: 'rgba(251, 191, 36, 0.3)' },
            stagnant: { accent: '#94a3b8', glow: 'rgba(148, 163, 184, 0.2)' }
        },
        gradient: 'linear-gradient(180deg, #1e3a5f 0%, #172554 50%, #0f172a 100%)'
    }
};

export const ThemeProvider = ({ children }) => {
    const [mode, setMode] = useState('dark');
    const theme = aquaticPalette[mode];

    const toggleTheme = () => setMode(m => m === 'light' ? 'dark' : 'light');

    return (
        <ThemeContext.Provider value={{ theme, mode, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
};

export const useTheme = () => {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};
