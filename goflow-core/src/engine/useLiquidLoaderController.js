import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

export const DEFAULT_LOADER_SCENES = [
  {
    title: 'Recalculando Fluxo de Vidro',
    sub: 'Sincronizando cortes analiticos com Oracle DB',
    step: 0
  },
  {
    title: 'Fundindo Camadas Financeiras',
    sub: 'Compondo agregacoes executivas em alta precisao',
    step: 1
  },
  {
    title: 'Refratando Metricas Criticas',
    sub: 'Aplicando periodo, centro de custo e natureza',
    step: 2
  },
  {
    title: 'Render Cinematico GoFlowOS',
    sub: 'Atualizando paineis com consistencia temporal',
    step: 3
  }
];

const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

const normalizeSceneIndex = (index, total) => {
  if (!Number.isFinite(index) || total <= 0) return 0;
  const normalized = Math.trunc(index) % total;
  return normalized < 0 ? normalized + total : normalized;
};

export const useLiquidLoaderController = (options = {}) => {
  const {
    scenes = DEFAULT_LOADER_SCENES,
    intervalMs = 2300,
    minVisibleMs = 900,
    exitMs = 260,
    autoCycle = true,
    initialVisible = false,
    initialSceneIndex = 0
  } = options;

  const sceneCount = scenes.length || 1;
  const [visible, setVisible] = useState(Boolean(initialVisible));
  const [exiting, setExiting] = useState(false);
  const [sceneIndex, setSceneIndex] = useState(() => normalizeSceneIndex(initialSceneIndex, sceneCount));

  const lockCountRef = useRef(0);
  const visibleAtRef = useRef(0);
  const hideDelayRef = useRef(null);
  const exitRef = useRef(null);

  const clearTimers = useCallback(() => {
    if (hideDelayRef.current) {
      clearTimeout(hideDelayRef.current);
      hideDelayRef.current = null;
    }

    if (exitRef.current) {
      clearTimeout(exitRef.current);
      exitRef.current = null;
    }
  }, []);

  const finishHide = useCallback(() => {
    clearTimers();
    setExiting(true);

    exitRef.current = setTimeout(() => {
      setVisible(false);
      setExiting(false);
      exitRef.current = null;
    }, exitMs);
  }, [clearTimers, exitMs]);

  const show = useCallback((sceneOffset = 0) => {
    clearTimers();

    lockCountRef.current += 1;
    if (lockCountRef.current > 1) return;

    setSceneIndex(normalizeSceneIndex(sceneOffset, sceneCount));
    visibleAtRef.current = now();
    setExiting(false);
    setVisible(true);
  }, [clearTimers, sceneCount]);

  const hide = useCallback((force = false) => {
    if (force) {
      lockCountRef.current = 0;
      clearTimers();
      setExiting(false);
      setVisible(false);
      return;
    }

    lockCountRef.current = Math.max(0, lockCountRef.current - 1);
    if (lockCountRef.current !== 0) return;

    const elapsed = now() - visibleAtRef.current;
    const waitMs = Math.max(0, minVisibleMs - elapsed);

    clearTimers();

    if (waitMs === 0) {
      finishHide();
      return;
    }

    hideDelayRef.current = setTimeout(() => {
      finishHide();
      hideDelayRef.current = null;
    }, waitMs);
  }, [clearTimers, finishHide, minVisibleMs]);

  useEffect(() => {
    if (!visible || !autoCycle || sceneCount <= 1) return undefined;

    const timer = setInterval(() => {
      setSceneIndex((current) => (current + 1) % sceneCount);
    }, intervalMs);

    return () => clearInterval(timer);
  }, [autoCycle, intervalMs, sceneCount, visible]);

  useEffect(() => {
    return () => {
      clearTimers();
    };
  }, [clearTimers]);

  const scene = useMemo(() => scenes[normalizeSceneIndex(sceneIndex, sceneCount)] ?? DEFAULT_LOADER_SCENES[0], [sceneCount, sceneIndex, scenes]);

  return {
    visible,
    exiting,
    sceneIndex,
    scene,
    phase: Number.isFinite(scene?.step) ? scene.step : normalizeSceneIndex(sceneIndex, sceneCount),
    show,
    hide,
    setSceneIndex: (index) => setSceneIndex(normalizeSceneIndex(index, sceneCount)),
    lockCount: lockCountRef.current
  };
};
