import React, { useMemo } from 'react';

const DEFAULT_STEPS = ['Preparar', 'Validar', 'Consolidar', 'Renderizar'];

const normalizeStep = (step, total) => {
  if (!Number.isFinite(step) || total <= 0) return 0;
  const normalized = Math.trunc(step) % total;
  return normalized < 0 ? normalized + total : normalized;
};

export function AidealMark({ className = '' }) {
  return (
    <svg
      className={`aideal-partnership-mark ${className}`.trim()}
      viewBox="0 0 92 92"
      role="img"
      aria-label="Símbolo AIDEAL"
    >
      <defs>
        <linearGradient id="aideal-mark-yellow" x1="22" y1="8" x2="72" y2="26" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#ffd646" />
          <stop offset="1" stopColor="#f3a912" />
        </linearGradient>
        <linearGradient id="aideal-mark-cyan" x1="18" y1="31" x2="75" y2="46" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#35c7f2" />
          <stop offset="1" stopColor="#2492d1" />
        </linearGradient>
        <linearGradient id="aideal-mark-red" x1="14" y1="56" x2="68" y2="72" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#ff2a35" />
          <stop offset="1" stopColor="#c90f1b" />
        </linearGradient>
        <filter id="aideal-mark-glow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="3.8" result="blur" />
          <feColorMatrix
            in="blur"
            type="matrix"
            values="0 0 0 0 0.20 0 0 0 0 0.78 0 0 0 0 0.95 0 0 0 0.62 0"
            result="glow"
          />
          <feMerge>
            <feMergeNode in="glow" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <g filter="url(#aideal-mark-glow)">
        <path
          className="aideal-mark-stroke aideal-mark-stroke-yellow"
          d="M29 18C40 15 50 11 64 6C68 5 71 7 71 11V17C71 20 69 22 66 23L25 35C21 36 18 34 18 30V27C18 23 21 20 29 18Z"
          fill="url(#aideal-mark-yellow)"
        />
        <path
          className="aideal-mark-stroke aideal-mark-stroke-cyan"
          d="M24 39C38 34 51 31 68 27C72 26 75 28 75 32V40C75 43 73 46 69 47L21 58C17 59 14 57 14 53V49C14 44 17 41 24 39Z"
          fill="url(#aideal-mark-cyan)"
        />
        <path
          className="aideal-mark-stroke aideal-mark-stroke-red"
          d="M19 63C32 59 45 56 62 53C66 52 69 54 69 58V66C69 69 67 72 63 73L17 82C13 83 10 81 10 77V73C10 68 13 65 19 63Z"
          fill="url(#aideal-mark-red)"
        />
      </g>
    </svg>
  );
}

export default function AidealPartnershipLoader({
  visible = false,
  exiting = false,
  scene,
  title,
  subtitle,
  steps = DEFAULT_STEPS,
}) {
  const activeStep = normalizeStep(scene?.step, steps.length || 1);
  const statusText = useMemo(() => {
    const activeTitle = title || 'AIDEAL × GoFlowOS';
    const activeSubtitle = subtitle || 'Processando inteligência financeira';
    return `${activeTitle}. ${activeSubtitle}. Etapa atual: ${steps[activeStep] || steps[0]}.`;
  }, [activeStep, steps, subtitle, title]);

  if (!visible) return null;

  return (
    <div
      className={`aideal-partnership-loader ${exiting ? 'is-exiting' : ''}`}
      data-loader-phase={String(activeStep)}
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <span className="aideal-sr-only">{statusText}</span>
      <div className="aideal-loader-technical-grid" aria-hidden="true" />
      <div className="aideal-loader-surface-noise" aria-hidden="true" />

      <div className="aideal-loader-stack">
        <section className="aideal-loader-stage" aria-hidden="true">
          <div className="aideal-loader-orbit">
            <span className="aideal-loader-orbit-line" />
            <span className="aideal-loader-data-dot dot-a" />
            <span className="aideal-loader-data-dot dot-b" />
            <span className="aideal-loader-data-dot dot-c" />
            <span className="aideal-loader-data-dot dot-d" />
          </div>
          <div className="aideal-loader-mark-shell">
            <AidealMark />
            <span className="aideal-loader-mark-sheen" />
          </div>
        </section>

        <div className="aideal-loader-copy">
          <span className="aideal-loader-kicker">Parceria operacional</span>
          <strong>{title || 'AIDEAL × GoFlowOS'}</strong>
          <p>{subtitle || 'Processando inteligência financeira'}</p>
          <div className="aideal-loader-steps">
            {steps.map((step, index) => (
              <span key={step} className={index === activeStep ? 'is-active' : ''}>
                {step}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
