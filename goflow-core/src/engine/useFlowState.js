import { useState, useCallback, useRef } from 'react';

// ============================================
// 1. FLOW CORE ENGINE - Estado Fluido
// ============================================

// Tipos de estado de fluxo
export const FlowStates = {
    LAMINAR: 'laminar',      // Fluxo suave e previsível
    TURBULENT: 'turbulent',  // Fluxo caótico, alta energia
    STAGNANT: 'stagnant'     // Estático, baixa energia
};

// Hook principal do FlowCore Engine
export const useFlowState = (initialValue, options = {}) => {
    const { viscosity = 0.5, transitionDuration = 300 } = options;
    const [value, setValue] = useState(initialValue);
    const [flowState, setFlowState] = useState(FlowStates.LAMINAR);
    const [isTransitioning, setIsTransitioning] = useState(false);
    const transitionRef = useRef(null);

    const transition = useCallback(async (newValue, customViscosity) => {
        const effectiveViscosity = customViscosity ?? viscosity;
        const duration = transitionDuration * (1 + effectiveViscosity);

        setIsTransitioning(true);
        setFlowState(FlowStates.TURBULENT);

        return new Promise((resolve) => {
            if (transitionRef.current) clearTimeout(transitionRef.current);

            transitionRef.current = setTimeout(() => {
                setValue(newValue);
                setFlowState(FlowStates.LAMINAR);
                setIsTransitioning(false);
                resolve(newValue);
            }, duration);
        });
    }, [viscosity, transitionDuration]);

    const equilibrium = useCallback(() => {
        return new Promise((resolve) => {
            if (!isTransitioning) {
                resolve(value);
            } else {
                const checkInterval = setInterval(() => {
                    if (!isTransitioning) {
                        clearInterval(checkInterval);
                        resolve(value);
                    }
                }, 50);
            }
        });
    }, [value, isTransitioning]);

    return {
        value,
        flowState,
        isTransitioning,
        transition,
        equilibrium,
        setDirect: setValue
    };
};
