import React, { useId } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

export default function OrcamentoLoadingScreen() {
  const reducedMotion = useReducedMotion();
  const id = useId().replaceAll(':', '');
  const sphereId = `${id}-sphere`;
  const strokeId = `${id}-stroke`;
  const draw = { duration: reducedMotion ? 0 : .6, ease: 'easeOut' };

  return (
    <motion.div
      className="orc-loading-screen"
      role="status"
      aria-label="Carregando Orçamento"
      aria-live="polite"
      aria-atomic="true"
      data-reduced-motion={Boolean(reducedMotion)}
      initial={false}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: reducedMotion ? 0 : .18 } }}
    >
      <svg className="orc-loading-mark" viewBox="0 0 128 128" fill="none" aria-hidden="true">
        <defs>
          <radialGradient id={sphereId} cx="30%" cy="24%" r="80%">
            <stop stopColor="#ffffff" />
            <stop offset=".24" stopColor="#c8edff" />
            <stop offset=".58" stopColor="#66b8ed" />
            <stop offset="1" stopColor="#20588d" />
          </radialGradient>
          <linearGradient id={strokeId} x1="14" y1="14" x2="114" y2="114" gradientUnits="userSpaceOnUse">
            <stop stopColor="#e4f6ff" />
            <stop offset=".48" stopColor="#81cdfa" />
            <stop offset="1" stopColor="#3876ad" />
          </linearGradient>
        </defs>
        <motion.circle cx="64" cy="64" r="50" stroke={`url(#${strokeId})`} strokeWidth="2.5"
          initial={{ pathLength: reducedMotion ? 1 : 0 }} animate={{ pathLength: 1 }} transition={draw} />
        <motion.g style={{ transformOrigin: '64px 64px' }}
          animate={{ rotate: reducedMotion ? 0 : 360 }}
          transition={reducedMotion ? { duration: 0 } : { duration: 3.6, ease: 'linear', repeat: Infinity }}>
          <motion.path d="M64 35 A29 29 0 0 1 64 93" stroke={`url(#${strokeId})`} strokeWidth="3.5" strokeLinecap="round"
            initial={{ pathLength: reducedMotion ? 1 : 0 }} animate={{ pathLength: 1 }} transition={draw} />
        </motion.g>
        <motion.circle cx="64" cy="64" r="12" fill={`url(#${sphereId})`}
          animate={{ opacity: reducedMotion ? 1 : [1, .78, 1] }}
          transition={reducedMotion ? { duration: 0 } : { duration: 2.4, ease: 'easeInOut', repeat: Infinity }} />
      </svg>
      <div className="orc-loading-copy" aria-hidden="true">
        <strong>goflowOS</strong>
        <span>Orçamento</span>
        <p>Carregando seus orçamentos…</p>
      </div>
    </motion.div>
  );
}
