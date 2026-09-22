export const windowMotion = (reducedMotion) => ({
  initial: { opacity: 0, y: reducedMotion ? 0 : 16, scale: reducedMotion ? 1 : 0.985 },
  animate: { opacity: 1, y: 0, scale: 1 },
  exit: { opacity: 0, y: reducedMotion ? 0 : 8, scale: reducedMotion ? 1 : 0.985 },
  transition: { duration: reducedMotion ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] },
});
