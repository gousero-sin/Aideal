import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useTheme } from '../theme/ThemeContext';
import { FlowStates } from '../engine/useFlowState';
import { X, Info, AlertTriangle, Check, Waves } from 'lucide-react';

// ============================================
// HYDRO UI COMPONENTS
// ============================================

// 3.1 FlowContainer
export const FlowContainer = ({ children, depth = 'surface', className = '', flowState = FlowStates.LAMINAR, style = {} }) => {
    const { theme } = useTheme();
    const depthStyle = theme.depths[depth];
    const flowStyle = theme.flowStates[flowState];

    return (
        <div
            className={`rounded-2xl p-6 transition-all duration-500 ${className}`}
            style={{
                backgroundColor: depthStyle.bg,
                color: depthStyle.text,
                border: `1px solid ${depthStyle.border}`,
                boxShadow: flowState === FlowStates.TURBULENT
                    ? `0 0 20px ${flowStyle.glow}, inset 0 0 10px ${flowStyle.glow}`
                    : `0 4px 20px rgba(0, 0, 0, 0.1)`,
                transform: flowState === FlowStates.TURBULENT ? 'scale(1.02)' : 'scale(1)',
                ...style
            }}
        >
            {children}
        </div>
    );
};

// 3.2 CurrentButton
export const CurrentButton = ({
    children,
    onClick,
    variant = 'primary',
    size = 'md',
    disabled = false,
    loading = false,
    icon: Icon = null
}) => {
    const { theme } = useTheme();
    const [buttonState, setButtonState] = useState('idle');
    const [ripples, setRipples] = useState([]);

    const handleClick = async (e) => {
        if (disabled || loading) return;

        // Create water ripple
        const rect = e.currentTarget.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const newRipple = { id: Date.now(), x, y };
        setRipples(prev => [...prev, newRipple]);
        setTimeout(() => setRipples(prev => prev.filter(r => r.id !== newRipple.id)), 600);

        setButtonState('active');
        setTimeout(() => {
            setButtonState('turbulent');
            setTimeout(() => {
                setButtonState('idle');
                onClick?.(e);
            }, 150);
        }, 100);
    };

    const sizes = {
        sm: 'px-3 py-1.5 text-sm',
        md: 'px-5 py-2.5 text-base',
        lg: 'px-7 py-3.5 text-lg'
    };

    const variants = {
        primary: {
            bg: theme.depths.deep.bg,
            text: theme.depths.deep.text,
            border: theme.depths.deep.border,
            hoverBg: theme.depths.abyss.bg
        },
        secondary: {
            bg: 'transparent',
            text: theme.depths.surface.text,
            border: theme.depths.deep.bg,
            hoverBg: theme.depths.shallow.bg
        },
        ghost: {
            bg: 'transparent',
            text: theme.depths.surface.text,
            border: 'transparent',
            hoverBg: theme.depths.shallow.bg
        }
    };

    const v = variants[variant];

    return (
        <button
            onClick={handleClick}
            disabled={disabled || loading}
            className={`
        relative overflow-hidden rounded-xl font-medium
        transition-all duration-300 ease-out
        flex items-center justify-center gap-2
        ${sizes[size]}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
      `}
            style={{
                backgroundColor: v.bg,
                color: v.text,
                border: `2px solid ${v.border}`,
                transform: buttonState === 'active' ? 'scale(0.97)' :
                    buttonState === 'turbulent' ? 'scale(1.02)' : 'scale(1)',
            }}
        >
            {/* Ripple Effect */}
            {ripples.map(ripple => (
                <span
                    key={ripple.id}
                    className="absolute rounded-full animate-ping"
                    style={{
                        left: ripple.x - 10,
                        top: ripple.y - 10,
                        width: 20,
                        height: 20,
                        backgroundColor: theme.flowStates.laminar.accent,
                        opacity: 0.4,
                        animationDuration: '0.6s'
                    }}
                />
            ))}

            {loading ? (
                <VortexLoader size="sm" />
            ) : (
                <>
                    {Icon && <Icon size={size === 'sm' ? 16 : size === 'md' ? 20 : 24} />}
                    <span className="relative z-10">{children}</span>
                </>
            )}
        </button>
    );
};

// 3.3 VortexLoader
export const VortexLoader = ({ size = 'md', label = '' }) => {
    const { theme } = useTheme();
    const sizes = { sm: 20, md: 40, lg: 64 };
    const s = sizes[size];

    return (
        <div className="flex flex-col items-center gap-2">
            <div className="relative" style={{ width: s, height: s }}>
                <motion.div
                    className="absolute inset-0 rounded-full border-2"
                    style={{ borderColor: theme.depths.deep.border, opacity: 0.3, borderStyle: 'dashed' }}
                    animate={{ rotate: 360 }}
                    transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
                />
                <motion.div
                    className="absolute inset-2 rounded-full border-2"
                    style={{ borderColor: theme.flowStates.turbulent.accent, borderStyle: 'dashed', borderTopColor: 'transparent' }}
                    animate={{ rotate: -360 }}
                    transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
                />
                <motion.div
                    className="absolute inset-4 rounded-full border-2"
                    style={{ borderColor: theme.flowStates.laminar.accent, borderStyle: 'dotted' }}
                    animate={{ rotate: 360 }}
                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                />
                <motion.div
                    className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
                    style={{ width: 8, height: 8, backgroundColor: theme.flowStates.laminar.accent }}
                    animate={{ scale: [1, 1.5, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                />
            </div>
            {label && (
                <span
                    className="text-sm font-medium animate-pulse"
                    style={{ color: theme.depths.surface.text }}
                >
                    {label}
                </span>
            )}
        </div>
    );
};

// 3.4 TidalModal
export const TidalModal = ({ isOpen, onClose, title, children, size = 'md' }) => {
    const { theme } = useTheme();

    const sizes = {
        sm: 'max-w-sm',
        md: 'max-w-lg',
        lg: 'max-w-2xl',
        xl: 'max-w-4xl'
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <motion.div
                        className="absolute inset-0"
                        style={{
                            background: `radial-gradient(circle at 50% 50%, transparent 0%, ${theme.depths.abyss.bg}dd 100%)`,
                            backdropFilter: 'blur(8px)'
                        }}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                    />

                    <motion.div
                        drag
                        dragConstraints={{ left: -300, right: 300, top: -200, bottom: 200 }}
                        dragElastic={0.1}
                        dragMomentum={true}
                        className={`relative ${sizes[size]} w-full rounded-2xl overflow-hidden shadow-2xl`}
                        style={{
                            backgroundColor: theme.depths.shallow.bg,
                            border: `1px solid ${theme.depths.deep.border}`,
                            boxShadow: `0 25px 50px -12px rgba(0, 0, 0, 0.4), 0 0 30px ${theme.flowStates.laminar.glow}`
                        }}
                        initial={{ scale: 0.9, opacity: 0, y: 50 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        exit={{ scale: 0.9, opacity: 0, y: 50 }}
                        transition={{ type: "spring", damping: 25, stiffness: 300 }}
                    >
                        <div
                            className="relative px-6 py-4 flex items-center justify-between cursor-grab active:cursor-grabbing"
                            style={{
                                backgroundColor: theme.depths.deep.bg,
                                borderBottom: `1px solid ${theme.depths.deep.border}`
                            }}
                        >
                            <h2 className="text-lg font-semibold flex items-center gap-2 select-none" style={{ color: theme.depths.deep.text }}>
                                <Waves size={20} />
                                {title}
                            </h2>

                            <button
                                onClick={onClose}
                                className="p-2 rounded-full transition-colors hover:bg-white/10"
                            >
                                <X size={20} style={{ color: theme.depths.deep.text }} />
                            </button>
                        </div>

                        <div className="p-6" style={{ color: theme.depths.shallow.text }}>
                            {children}
                        </div>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    );
};

// 3.5 FlowCard
export const FlowCard = ({ title, value, unit, icon: Icon, trend, flowState = FlowStates.LAMINAR }) => {
    const { theme } = useTheme();

    const trendColors = {
        up: theme.flowStates.laminar.accent,
        down: '#ef4444',
        stable: theme.flowStates.stagnant.accent
    };

    return (
        <FlowContainer depth="shallow" flowState={flowState}>
            <div className="flex items-start justify-between mb-4">
                <div
                    className="p-3 rounded-xl"
                    style={{ backgroundColor: theme.depths.deep.bg + '40' }}
                >
                    {Icon && <Icon size={24} style={{ color: theme.flowStates.laminar.accent }} />}
                </div>

                {trend && (
                    <div
                        className="flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium"
                        style={{
                            backgroundColor: trendColors[trend] + '20',
                            color: trendColors[trend]
                        }}
                    >
                        {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
                        {trend === 'up' ? '+12%' : trend === 'down' ? '-5%' : '0%'}
                    </div>
                )}
            </div>

            <div className="space-y-1">
                <p className="text-sm opacity-70">{title}</p>
                <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold">{value}</span>
                    {unit && <span className="text-sm opacity-60">{unit}</span>}
                </div>
            </div>

            <div
                className="mt-4 h-1 rounded-full overflow-hidden"
                style={{ backgroundColor: theme.depths.deep.bg + '30' }}
            >
                <div
                    className={`h-full rounded-full transition-all duration-1000 ${flowState === FlowStates.TURBULENT ? 'animate-pulse' : ''
                        }`}
                    style={{
                        width: flowState === FlowStates.LAMINAR ? '75%' :
                            flowState === FlowStates.TURBULENT ? '90%' : '30%',
                        backgroundColor: theme.flowStates[flowState].accent
                    }}
                />
            </div>
        </FlowContainer>
    );
};

// 3.6 FlowNotification
export const FlowNotification = ({ type = 'info', message, onDismiss }) => {
    const { theme } = useTheme();

    const types = {
        info: { icon: Info, color: theme.flowStates.laminar.accent },
        warning: { icon: AlertTriangle, color: theme.flowStates.turbulent.accent },
        success: { icon: Check, color: '#22c55e' },
        error: { icon: X, color: '#ef4444' }
    };

    const t = types[type];
    const Icon = t.icon;

    return (
        <div
            className="flex items-center gap-3 px-4 py-3 rounded-xl animate-in slide-in-from-top-2"
            style={{
                backgroundColor: theme.depths.shallow.bg,
                border: `1px solid ${t.color}40`,
                boxShadow: `0 4px 20px ${t.color}20`
            }}
        >
            <div
                className="p-1.5 rounded-full"
                style={{ backgroundColor: t.color + '20' }}
            >
                <Icon size={16} style={{ color: t.color }} />
            </div>

            <span className="flex-1 text-sm" style={{ color: theme.depths.shallow.text }}>
                {message}
            </span>

            {onDismiss && (
                <button
                    onClick={onDismiss}
                    className="p-1 rounded-full hover:bg-white/10 transition-colors"
                >
                    <X size={14} style={{ color: theme.depths.shallow.text }} />
                </button>
            )}
        </div>
    );
};
