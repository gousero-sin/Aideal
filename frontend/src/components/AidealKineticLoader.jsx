import React, { useId, useMemo, useState } from 'react';
import {
  DEFAULT_STEPS,
  SPEED_LINES,
  STROKES,
  STROKE_MASK,
  STROKE_PATH,
  STROKE_VIEWBOX,
  buildStatusText,
  normalizeStep,
} from './aidealKineticLoaderModel';
import '../styles/aideal-kinetic-loader.css';

const VIEWBOX = `0 0 ${STROKE_VIEWBOX.width} ${STROKE_VIEWBOX.height}`;
const GHOSTS = Object.freeze(['far', 'near']);
const ROOT_STYLE = Object.freeze({ '--akl-mask': STROKE_MASK });

const strokeStyle = (stroke, index) => ({
  '--akl-left': `${stroke.left}%`,
  '--akl-top': `${stroke.top}%`,
  '--akl-width': `${stroke.width}%`,
  '--akl-dir': stroke.dir,
  '--akl-index': index,
  '--akl-intro-delay': `${stroke.introDelay}ms`,
  '--akl-loop-delay': `${stroke.loopDelay}ms`,
  '--akl-exit-delay': `${stroke.exitDelay}ms`,
  '--akl-c0': stroke.colors[0],
  '--akl-c1': stroke.colors[1],
  '--akl-c2': stroke.colors[2],
});

const speedLineStyle = (line) => ({
  '--akl-top': `${line.top}%`,
  '--akl-w': `${line.width}vmin`,
  '--akl-dur': `${line.duration}ms`,
  '--akl-delay': `${line.delay}ms`,
  '--akl-o': line.opacity,
  '--akl-c': line.color,
});

function StrokeShape({ symbolId, gradientId }) {
  return (
    <svg className="akl-stroke-svg" viewBox={VIEWBOX} focusable="false">
      <use
        href={`#${symbolId}`}
        width={STROKE_VIEWBOX.width}
        height={STROKE_VIEWBOX.height}
        fill={`url(#${gradientId})`}
      />
    </svg>
  );
}

function KineticStroke({ stroke, index, symbolId, gradientId }) {
  return (
    <div className={`akl-stroke akl-stroke--${stroke.id}`} style={strokeStyle(stroke, index)}>
      <div className="akl-stroke-exit">
        {GHOSTS.map((ghost) => (
          <div key={ghost} className={`akl-ghost akl-ghost--${ghost}`}>
            <div className="akl-ghost-loop">
              <span className="akl-ghost-body" />
            </div>
          </div>
        ))}
        <div className="akl-stroke-intro">
          <div className="akl-stroke-loop">
            <div className="akl-stroke-body">
              <span className="akl-stroke-glow">
                <StrokeShape symbolId={symbolId} gradientId={gradientId} />
              </span>
              <StrokeShape symbolId={symbolId} gradientId={gradientId} />
              <span className="akl-stroke-light">
                <span className="akl-stroke-flash" />
                <span className="akl-stroke-sheen" />
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AidealKineticLoader({
  visible = false,
  exiting = false,
  scene,
  title,
  subtitle,
  steps = DEFAULT_STEPS,
}) {
  const uid = `akl-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  // show() durante a saída devolve exiting=false sem desmontar; sem remontar a
  // cena, as pinceladas em pleno voo saltariam de volta ao centro. Cada
  // reabertura ganha uma chave nova e repete a entrada; zera ao esconder.
  const [wasExiting, setWasExiting] = useState(exiting);
  const [replays, setReplays] = useState(0);
  if (exiting !== wasExiting) {
    setWasExiting(exiting);
    if (wasExiting && visible) setReplays((count) => count + 1);
  }
  if (!visible && replays !== 0) setReplays(0);
  const activeStep = normalizeStep(scene?.step, steps?.length || DEFAULT_STEPS.length);
  const statusText = useMemo(
    () => buildStatusText({ title, subtitle, steps, activeStep }),
    [activeStep, steps, subtitle, title],
  );

  if (!visible) return null;

  const symbolId = `${uid}-stroke`;

  return (
    <div
      key={replays}
      className={`aideal-kinetic-loader${exiting ? ' is-exiting' : ''}${replays > 0 ? ' is-replay' : ''}`}
      data-loader-phase={String(activeStep)}
      style={ROOT_STYLE}
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <span className="aideal-sr-only">{statusText}</span>

      <svg className="akl-defs" aria-hidden="true" focusable="false">
        <defs>
          <symbol id={symbolId} viewBox={VIEWBOX}>
            <path d={STROKE_PATH} />
          </symbol>
          {STROKES.map((stroke) => (
            <linearGradient key={stroke.id} id={`${uid}-${stroke.id}`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor={stroke.colors[0]} />
              <stop offset="0.36" stopColor={stroke.colors[1]} />
              <stop offset="1" stopColor={stroke.colors[2]} />
            </linearGradient>
          ))}
        </defs>
      </svg>

      <div className="akl-backdrop" aria-hidden="true" />

      <div className="akl-auroras" aria-hidden="true">
        <span className="akl-aurora akl-aurora--yellow" />
        <span className="akl-aurora akl-aurora--blue" />
        <span className="akl-aurora akl-aurora--red" />
      </div>

      <div className="akl-speed" aria-hidden="true">
        <div className="akl-speed-field">
          {SPEED_LINES.map((line) => (
            <span key={`${line.top}-${line.width}`} className="akl-speed-line" style={speedLineStyle(line)} />
          ))}
        </div>
      </div>

      <div className="akl-perspective" aria-hidden="true">
        <div className="akl-stage">
          <div className="akl-tilt">
            <span className="akl-ring" />
            <div className="akl-strokes">
              {STROKES.map((stroke, index) => (
                <KineticStroke
                  key={stroke.id}
                  stroke={stroke}
                  index={index}
                  symbolId={symbolId}
                  gradientId={`${uid}-${stroke.id}`}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
