import React, { useId } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import '../../styles/orcamento-loader.css';

const WORDMARK = 'goflowOS';
// Órbita com as quatro partes do preço (diretos, indiretos, lucro, impostos): comprimento e
// posição em centésimos da volta, com um respiro entre elas.
const ORBIT = Object.freeze([
  Object.freeze({ part: 'diretos', length: 44, start: 0 }),
  Object.freeze({ part: 'indiretos', length: 12, start: 49 }),
  Object.freeze({ part: 'lucro', length: 15, start: 66 }),
  Object.freeze({ part: 'impostos', length: 11, start: 86 }),
]);
const TRAILS = Object.freeze(['far', 'near', 'head']);
const SEMICIRCLE = 'M200 110 A90 90 0 0 1 200 290';

/**
 * Tela de entrada do Orçamento. A marca GoFlow (anel, semicírculo e esfera) se monta em
 * sequência e segue viva enquanto os dados carregam. Toda a coreografia é CSS: o SVG não muda
 * no DOM, e com movimento reduzido a marca aparece já montada e parada.
 */
export default function OrcamentoLoadingScreen() {
  const reducedMotion = useReducedMotion();
  const id = useId().replaceAll(':', '');
  const sphereId = `${id}-sphere`;
  const strokeId = `${id}-stroke`;

  return (
    <motion.div
      className="orc-loading-screen"
      role="status"
      aria-label="Carregando Orçamento"
      aria-live="polite"
      aria-atomic="true"
      data-reduced-motion={Boolean(reducedMotion)}
      initial={false}
      animate={{ opacity: 1, scale: 1 }}
      exit={reducedMotion
        ? { opacity: 0, transition: { duration: 0 } }
        : { opacity: 0, scale: 1.05, transition: { duration: 0.3, ease: [0.4, 0, 1, 1] } }}
    >
      <span aria-hidden="true" className="orc-lm-sweep" />
      <svg className="orc-loading-mark" viewBox="0 0 400 400" fill="none" aria-hidden="true">
        <defs>
          <radialGradient id={sphereId} cx="32%" cy="26%" r="80%">
            <stop stopColor="#ffffff" />
            <stop offset=".24" stopColor="#d3f0ff" />
            <stop offset=".58" stopColor="#5fb2ec" />
            <stop offset="1" stopColor="#1b4f86" />
          </radialGradient>
          <linearGradient id={strokeId} x1="50" y1="50" x2="350" y2="350" gradientUnits="userSpaceOnUse">
            <stop stopColor="#eaf7ff" />
            <stop offset=".5" stopColor="#8fd5ff" />
            <stop offset="1" stopColor="#2f8bd8" />
          </linearGradient>
        </defs>

        <circle className="orc-lm-ticks" cx="200" cy="200" r="190" pathLength="240" />
        <g className="orc-lm-orbit">
          {ORBIT.map(({ part, length, start }, index) => (
            <circle className="orc-lm-arc" cx="200" cy="200" data-part={part} key={part} pathLength="100" r="172"
              style={{ '--orc-lm-length': length, '--orc-lm-start': start, '--orc-lm-index': index }} />
          ))}
        </g>
        <circle className="orc-lm-ring" cx="200" cy="200" pathLength="1" r="150" stroke={`url(#${strokeId})`} />
        <g className="orc-lm-counter">
          <circle cx="200" cy="200" pathLength="100" r="126" />
        </g>
        {TRAILS.map((trail) => (
          <g className="orc-lm-whip" data-trail={trail} key={trail}>
            <path d={SEMICIRCLE} pathLength="1" stroke={`url(#${strokeId})`} />
          </g>
        ))}
        <circle className="orc-lm-shock" cx="200" cy="200" r="38" />
        <circle className="orc-lm-shock orc-lm-shock--late" cx="200" cy="200" r="38" />
        <circle className="orc-lm-core" cx="200" cy="200" r="38" fill={`url(#${sphereId})`} />
      </svg>
      <div className="orc-loading-copy" aria-hidden="true">
        <strong>
          {[...WORDMARK].map((letter, index) => (
            <span key={`${letter}-${index}`} style={{ '--orc-lm-index': index }}>{letter}</span>
          ))}
        </strong>
        <span>Orçamento</span>
        <i className="orc-lm-progress" />
      </div>
    </motion.div>
  );
}
