import React, { useEffect } from 'react';
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from 'framer-motion';
import { formatMoney } from './editorShared';

/** Número com contagem animada até o novo valor; com movimento reduzido troca direto. */
export default function AnimatedValue({ className, format = formatMoney, value }) {
  const reducedMotion = useReducedMotion();
  const target = Number.isFinite(Number(value)) ? Number(value) : 0;
  const current = useMotionValue(target);
  const text = useTransform(current, (latest) => format(latest));

  useEffect(() => {
    if (reducedMotion) {
      current.set(target);
      return undefined;
    }
    const controls = animate(current, target, { duration: 0.45, ease: [0.22, 1, 0.36, 1] });
    return () => controls.stop();
  }, [current, reducedMotion, target]);

  return <motion.span className={className}>{text}</motion.span>;
}
