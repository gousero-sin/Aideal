import React, { useMemo } from 'react';
import { DEFAULT_LOADER_SCENES } from '../engine/useLiquidLoaderController';

const classNames = (...names) => names.filter(Boolean).join(' ');

const normalizeSceneIndex = (index, total) => {
  if (!Number.isFinite(index) || total <= 0) return 0;
  const normalized = Math.trunc(index) % total;
  return normalized < 0 ? normalized + total : normalized;
};

const DEFAULT_STEP_LABELS = ['Ingestao', 'Fusao', 'Refracao', 'Render'];

export const LiquidIntelligenceLoader = ({
  visible = true,
  exiting = false,
  scene,
  scenes = DEFAULT_LOADER_SCENES,
  sceneIndex = 0,
  steps = DEFAULT_STEP_LABELS,
  title,
  subtitle,
  className = '',
  keepMounted = false
}) => {
  const totalScenes = scenes.length || 1;

  const activeScene = useMemo(() => {
    if (scene) return scene;
    return scenes[normalizeSceneIndex(sceneIndex, totalScenes)] ?? DEFAULT_LOADER_SCENES[0];
  }, [scene, sceneIndex, scenes, totalScenes]);

  const activeTitle = title ?? activeScene?.title ?? DEFAULT_LOADER_SCENES[0].title;
  const activeSubtitle = subtitle ?? activeScene?.sub ?? DEFAULT_LOADER_SCENES[0].sub;
  const phase = Number.isFinite(activeScene?.step)
    ? activeScene.step
    : normalizeSceneIndex(sceneIndex, steps.length || 1);

  if (!visible && !keepMounted) return null;

  return (
    <div
      className={classNames(
        'goflow-loader-container',
        !visible && 'hidden',
        exiting && 'is-exiting',
        className
      )}
      data-loader-phase={String(phase)}
      aria-live="polite"
      aria-atomic="true"
      role="status"
    >
      <div className="goflow-liquid-intelligence-stage" aria-hidden="true">
        <div className="goflow-liquid-atmo-field" />
        <div className="goflow-liquid-depth-fog" />

        <div className="goflow-liquid-orb">
          <div className="goflow-liquid-orb-fluid">
            <div className="goflow-liquid-orb-fill" />
            <div className="goflow-liquid-orb-current current-a" />
            <div className="goflow-liquid-orb-current current-b" />
            <div className="goflow-liquid-orb-current current-c" />
            <div className="goflow-liquid-orb-caustic" />
            <div className="goflow-liquid-orb-ripple ripple-a" />
            <div className="goflow-liquid-orb-ripple ripple-b" />
            <span className="goflow-liquid-orb-particle lp-1" />
            <span className="goflow-liquid-orb-particle lp-2" />
            <span className="goflow-liquid-orb-particle lp-3" />
            <span className="goflow-liquid-orb-particle lp-4" />
            <span className="goflow-liquid-orb-particle lp-5" />
          </div>
          <div className="goflow-liquid-orb-refraction" />
          <div className="goflow-liquid-orb-gloss" />
          <div className="goflow-liquid-orb-shell" />
          <div className="goflow-liquid-orb-aura" />
        </div>
      </div>

      <div className="goflow-loader-text">
        <span className="goflow-loading-pulse">{activeTitle}</span>
        <span className="goflow-loading-sub">{activeSubtitle}</span>
        <div className="goflow-loading-steps">
          {steps.map((label, index) => (
            <span
              key={label}
              className={classNames('goflow-loading-step', index === phase && 'is-active')}
            >
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

const DEFAULT_BADGES = ['Real-time SQL', '7 Relatorios', 'Conexao Segura'];

const DEFAULT_METRICS = [
  { label: 'Pool', value: 'SID ORA' },
  { label: 'Latencia', value: '18ms' },
  { label: 'Canal', value: 'Encrypted TLS' }
];

export const LiquidDbConnectionLoader = ({
  title = 'Conectando ao Oracle DB...',
  subtitle = 'Buscando inteligencia do ERP',
  badges = DEFAULT_BADGES,
  metrics = DEFAULT_METRICS,
  className = ''
}) => {
  return (
    <div className={classNames('goflow-liquid-db-shell', className)}>
      <div className="goflow-liquid-fume-layer" aria-hidden="true" />

      <div className="goflow-db-connection-animation goflow-liquid-loader" aria-hidden="true">
        <div className="goflow-liquid-halo" />

        <div className="goflow-liquid-bubble-field">
          <span className="goflow-liquid-bubble b1" />
          <span className="goflow-liquid-bubble b2" />
          <span className="goflow-liquid-bubble b3" />
          <span className="goflow-liquid-bubble b4" />
          <span className="goflow-liquid-bubble b5" />
          <span className="goflow-liquid-bubble b6" />
          <span className="goflow-liquid-bubble b7" />
          <span className="goflow-liquid-bubble b8" />
          <span className="goflow-liquid-bubble b9" />
        </div>

        <div className="goflow-liquid-core goflow-liquid-card-assembling">
          <div className="goflow-liquid-core-reflection" />
          <div className="goflow-liquid-core-refract" />
          <svg className="goflow-liquid-core-logo" viewBox="0 0 40 40" fill="none" role="img" aria-label="GoFlow">
            <circle cx="20" cy="20" r="16.4" stroke="currentColor" strokeWidth="2.4" />
            <path
              d="M13 20c0-4 3-7 7-7s7 3 7 7-3 7-7 7"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
            />
            <circle cx="20" cy="20" r="3.2" fill="currentColor" />
          </svg>
        </div>

        <div className="goflow-liquid-pulse-ring ring-1" />
        <div className="goflow-liquid-pulse-ring ring-2" />

        <div className="goflow-liquid-data-stream">
          <span style={{ '--stream-delay': '0s' }} />
          <span style={{ '--stream-delay': '0.45s' }} />
          <span style={{ '--stream-delay': '0.9s' }} />
          <span style={{ '--stream-delay': '1.25s' }} />
        </div>
      </div>

      <div className="goflow-upload-text-main goflow-db-text-pulse">{title}</div>
      <div className="goflow-upload-text-sub goflow-db-text-fade">{subtitle}</div>

      <div className="goflow-upload-badge-row">
        {badges.map((badge, index) => (
          <span
            key={badge}
            className="goflow-upload-badge goflow-db-badge-glow"
            style={{ '--delay': `${0.15 + (index * 0.22)}s` }}
          >
            {badge}
          </span>
        ))}
      </div>

      <div className="goflow-db-metrics-row">
        {metrics.map((metric) => (
          <div key={metric.label} className="goflow-db-metric">
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </div>
        ))}
      </div>
    </div>
  );
};
