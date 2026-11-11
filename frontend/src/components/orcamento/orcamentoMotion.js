// Variantes de motion compartilhadas pelo Orçamento (carteira, diálogos e editores).
// Todas as fábricas recebem `reducedMotion` (resultado de useReducedMotion()) e
// retornam props prontas para espalhar em um elemento `motion.*`:
//   <motion.div {...backdropMotion(reduced)} />
// Com movimento reduzido, apenas a opacidade muda e as durações vão a zero.

const EASE_OUT = [0.22, 1, 0.36, 1];

// Mola suave usada em janelas, selos e reordenação de cartões.
export const springSoft = Object.freeze({ type: 'spring', stiffness: 380, damping: 34, mass: 0.9 });

const instant = Object.freeze({ duration: 0 });

// Camada de fundo (overlay fixed inset:0): só opacidade, nunca escala.
export const backdropMotion = (reducedMotion) => ({
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: reducedMotion ? instant : { duration: 0.2, ease: EASE_OUT },
});

// Janela/diálogo: escala + deslocamento com mola. Aplicar no elemento da janela,
// dentro do backdrop, para a camada de fundo não escalar junto.
export const windowMotion = (reducedMotion) => ({
  initial: { opacity: 0, y: reducedMotion ? 0 : 16, scale: reducedMotion ? 1 : 0.97 },
  animate: { opacity: 1, y: 0, scale: 1 },
  exit: {
    opacity: 0,
    y: reducedMotion ? 0 : 8,
    scale: reducedMotion ? 1 : 0.98,
    transition: reducedMotion ? instant : { duration: 0.16, ease: EASE_OUT },
  },
  transition: reducedMotion ? instant : { ...springSoft, opacity: { duration: 0.18, ease: EASE_OUT } },
});

// Itens de lista/linhas de tabela com entrada escalonada.
// `index` define o atraso (limitado para listas longas não demorarem).
export const listItemMotion = (reducedMotion, index = 0) => ({
  initial: { opacity: 0, y: reducedMotion ? 0 : 10 },
  animate: {
    opacity: 1,
    y: 0,
    transition: reducedMotion
      ? instant
      : { ...springSoft, delay: Math.min(Math.max(index, 0), 8) * 0.04, opacity: { duration: 0.2, delay: Math.min(Math.max(index, 0), 8) * 0.04 } },
  },
  exit: {
    opacity: 0,
    y: reducedMotion ? 0 : -6,
    transition: reducedMotion ? instant : { duration: 0.14, ease: EASE_OUT },
  },
});
