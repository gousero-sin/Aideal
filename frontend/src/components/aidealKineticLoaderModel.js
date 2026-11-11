// Modelo da tela de carregamento "Pinceladas Cinéticas".
//
// Geometria medida no símbolo do logo AIDEAL: cada pincelada é uma barra de
// 630×184 com os cantos superior-esquerdo e inferior-direito arredondados
// (raio 149) e cortes verticais nas pontas; as três têm o mesmo tamanho e
// ficam empilhadas com passo de 0,3596 da largura. A inclinação de 10° vem de
// um skewY no container (ver aideal-kinetic-loader.css), como no logo.

export const DEFAULT_TITLE = 'AIDEAL × GoFlowOS';
export const DEFAULT_SUBTITLE = 'Processando inteligência financeira';
export const DEFAULT_STEPS = Object.freeze(['Preparar', 'Validar', 'Consolidar', 'Renderizar']);

export const normalizeStep = (step, total) => {
  if (!Number.isFinite(step) || !(total > 0)) return 0;
  return ((Math.trunc(step) % total) + total) % total;
};

export const buildStatusText = ({ title, subtitle, steps, activeStep } = {}) => {
  const list = Array.isArray(steps) && steps.length > 0 ? steps : DEFAULT_STEPS;
  const step = list[normalizeStep(activeStep, list.length)];
  return `${title || DEFAULT_TITLE}. ${subtitle || DEFAULT_SUBTITLE}. Etapa atual: ${step}.`;
};

export const STROKE_VIEWBOX = Object.freeze({ width: 630, height: 184 });

export const STROKE_PATH = 'M0 184V149A149 149 0 0 1 149 0H630V35A149 149 0 0 1 481 184Z';

// Máscara CSS com o mesmo contorno: recorta o flash de aterrissagem e o brilho
// que varre a pincelada. preserveAspectRatio='none' estica ao container, que
// já tem a proporção do viewBox.
const STROKE_MASK_SVG = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 ${STROKE_VIEWBOX.width} ${STROKE_VIEWBOX.height}' preserveAspectRatio='none'><path d='${STROKE_PATH}'/></svg>`;

export const STROKE_MASK = `url("data:image/svg+xml,${encodeURIComponent(STROKE_MASK_SVG).replace(/'/g, '%27')}")`;

// Posição em % do palco quadrado (antes do skew). Cores: cabeça mais escura à
// esquerda, cor da marca no corpo e ponta mais clara, como no logo.
const stroke = (id, top, dir, introDelay, loopDelay, exitDelay, colors) => Object.freeze({
  id,
  left: 13,
  top,
  width: 74,
  dir,
  introDelay,
  loopDelay,
  exitDelay,
  colors: Object.freeze(colors),
});

export const STROKES = Object.freeze([
  stroke('yellow', 12.58, 1, 80, 0, 0, ['#F29A00', '#FFB800', '#FFCB3D']),
  stroke('blue', 39.19, -1, 200, 180, 50, ['#0A7FEF', '#00AEFF', '#3FCBF6']),
  stroke('red', 65.8, 1, 320, 360, 100, ['#BE0A10', '#E3141B', '#FF3D3D']),
]);

// top em % do campo de linhas, width em vmin, duration/delay em ms.
const line = (top, width, duration, delay, opacity, color) => Object.freeze({
  top,
  width,
  duration,
  delay,
  opacity,
  color,
});

export const SPEED_LINES = Object.freeze([
  line(6, 26, 1100, -380, 0.18, '#35C7F2'),
  line(12, 38, 820, -610, 0.32, '#FFFFFF'),
  line(19, 22, 1450, -1180, 0.14, '#FFB800'),
  line(25, 42, 760, -90, 0.42, '#35C7F2'),
  line(32, 30, 1260, -905, 0.22, '#FFFFFF'),
  line(38, 18, 980, -470, 0.3, '#E3141B'),
  line(45, 34, 1600, -1320, 0.16, '#FFFFFF'),
  line(51, 24, 700, -260, 0.45, '#00AEFF'),
  line(58, 40, 1180, -760, 0.2, '#FFB800'),
  line(64, 20, 900, -55, 0.36, '#FFFFFF'),
  line(71, 36, 1380, -1010, 0.15, '#35C7F2'),
  line(77, 28, 790, -540, 0.4, '#E3141B'),
  line(84, 42, 1520, -330, 0.12, '#FFFFFF'),
  line(92, 24, 1040, -820, 0.26, '#00AEFF'),
]);
