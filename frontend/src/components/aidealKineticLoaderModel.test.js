import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_STEPS,
  SPEED_LINES,
  STROKES,
  STROKE_MASK,
  STROKE_PATH,
  STROKE_VIEWBOX,
  buildStatusText,
  normalizeStep,
} from './aidealKineticLoaderModel.js';

test('normalizeStep mantém a etapa dentro do total, inclusive com negativos e frações', () => {
  assert.equal(normalizeStep(0, 4), 0);
  assert.equal(normalizeStep(5, 4), 1);
  assert.equal(normalizeStep(-1, 4), 3);
  assert.equal(normalizeStep(-6, 4), 2);
  assert.equal(normalizeStep(2.9, 4), 2);
  assert.equal(normalizeStep(-0.5, 4), 0);
});

test('normalizeStep devolve zero para etapa inválida ou total vazio', () => {
  assert.equal(normalizeStep(Number.NaN, 4), 0);
  assert.equal(normalizeStep(undefined, 4), 0);
  assert.equal(normalizeStep(Number.POSITIVE_INFINITY, 4), 0);
  assert.equal(normalizeStep(2, 0), 0);
  assert.equal(normalizeStep(2, -3), 0);
  assert.equal(normalizeStep(2, Number.NaN), 0);
});

test('buildStatusText usa os textos padrão quando não recebe props', () => {
  assert.equal(
    buildStatusText(),
    'AIDEAL × GoFlowOS. Processando inteligência financeira. Etapa atual: Preparar.',
  );
});

test('buildStatusText usa título, subtítulo e a etapa ativa normalizada', () => {
  assert.equal(
    buildStatusText({
      title: 'Painel DRE',
      subtitle: 'Carregando dados',
      steps: ['Buscar', 'Somar', 'Exibir'],
      activeStep: 4,
    }),
    'Painel DRE. Carregando dados. Etapa atual: Somar.',
  );
});

test('buildStatusText volta para as etapas padrão quando a lista vem vazia', () => {
  assert.deepEqual(DEFAULT_STEPS, ['Preparar', 'Validar', 'Consolidar', 'Renderizar']);
  assert.equal(
    buildStatusText({ steps: [], activeStep: 2 }),
    'AIDEAL × GoFlowOS. Processando inteligência financeira. Etapa atual: Consolidar.',
  );
});

test('STROKES descreve as três pinceladas do símbolo, na ordem e nas cores da marca', () => {
  assert.equal(STROKES.length, 3);
  assert.deepEqual(STROKES.map(({ id }) => id), ['yellow', 'blue', 'red']);
  assert.deepEqual(STROKES.map(({ colors }) => colors[1]), ['#FFB800', '#00AEFF', '#E3141B']);
  STROKES.forEach(({ colors }) => assert.equal(colors.length, 3));
  assert.deepEqual(STROKES.map(({ dir }) => dir), [1, -1, 1]);
});

test('STROKES alinha as pinceladas como no logo: mesma largura, mesma borda e passo constante', () => {
  const [yellow, blue, red] = STROKES;
  STROKES.forEach((stroke) => {
    assert.equal(stroke.left, yellow.left);
    assert.equal(stroke.width, yellow.width);
  });
  const pitch = blue.top - yellow.top;
  assert.ok(Math.abs(red.top - blue.top - pitch) < 0.02);
  assert.ok(Math.abs(yellow.left * 2 + yellow.width - 100) < 0.02, 'símbolo centrado na horizontal');
  const strokeHeight = (yellow.width * STROKE_VIEWBOX.height) / STROKE_VIEWBOX.width;
  const symbolBottom = red.top + strokeHeight;
  assert.ok(Math.abs(yellow.top + symbolBottom - 100) < 0.05, 'símbolo centrado na vertical');
});

test('STROKES escalona entrada, revezamento e saída da primeira para a última pincelada', () => {
  ['introDelay', 'loopDelay', 'exitDelay'].forEach((key) => {
    const delays = STROKES.map((stroke) => stroke[key]);
    assert.deepEqual([...delays].sort((a, b) => a - b), delays, `${key} crescente`);
  });
  assert.deepEqual(STROKES.map(({ introDelay }) => introDelay), [80, 200, 320]);
  assert.deepEqual(STROKES.map(({ loopDelay }) => loopDelay), [0, 180, 360]);
  assert.deepEqual(STROKES.map(({ exitDelay }) => exitDelay), [0, 50, 100]);
});

test('SPEED_LINES tem 14 linhas fixas, já espalhadas no tempo e dentro das faixas do plano', () => {
  assert.equal(SPEED_LINES.length, 14);
  SPEED_LINES.forEach((line) => {
    assert.ok(line.delay <= 0, 'delay negativo para nascer espalhada');
    assert.ok(-line.delay < line.duration);
    assert.ok(line.top >= 0 && line.top <= 100);
    assert.ok(line.width >= 18 && line.width <= 42);
    assert.ok(line.duration >= 700 && line.duration <= 1600);
    assert.ok(line.opacity >= 0.12 && line.opacity <= 0.45);
    assert.match(line.color, /^#[0-9A-F]{6}$/);
  });
});

test('modelo é imutável', () => {
  assert.ok(Object.isFrozen(STROKES));
  assert.ok(Object.isFrozen(SPEED_LINES));
  assert.ok(Object.isFrozen(DEFAULT_STEPS));
  assert.ok(Object.isFrozen(STROKE_VIEWBOX));
  STROKES.forEach((stroke) => {
    assert.ok(Object.isFrozen(stroke));
    assert.ok(Object.isFrozen(stroke.colors));
  });
  SPEED_LINES.forEach((line) => assert.ok(Object.isFrozen(line)));
});

test('STROKE_PATH é um contorno fechado dentro do viewBox da pincelada', () => {
  assert.match(STROKE_PATH, /^M/);
  assert.match(STROKE_PATH, /Z$/);
  const numbers = STROKE_PATH.match(/-?\d+(\.\d+)?/g).map(Number);
  numbers.forEach((value) => {
    assert.ok(value >= 0 && value <= STROKE_VIEWBOX.width);
  });
});

test('STROKE_MASK recorta brilho e flash no mesmo contorno da pincelada, esticado ao container', () => {
  const match = STROKE_MASK.match(/^url\("data:image\/svg\+xml,(.+)"\)$/);
  assert.ok(match, 'url() com data URI de SVG');
  assert.doesNotMatch(match[1], /["'<>#\s]/, 'payload codificado para caber em url("...")');
  const svg = decodeURIComponent(match[1]);
  assert.match(svg, /xmlns='http:\/\/www\.w3\.org\/2000\/svg'/);
  assert.match(svg, new RegExp(`viewBox='0 0 ${STROKE_VIEWBOX.width} ${STROKE_VIEWBOX.height}'`));
  assert.match(svg, /preserveAspectRatio='none'/);
  assert.ok(svg.includes(`d='${STROKE_PATH}'`));
});
