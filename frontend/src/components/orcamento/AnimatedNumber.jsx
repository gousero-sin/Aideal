import React, { useEffect, useRef, useState } from 'react';
import { animate, useReducedMotion } from 'framer-motion';

// Conta do valor anterior até o novo. Leitores de tela recebem só o valor final.
export default function AnimatedNumber({ format = String, value }) {
  const reducedMotion = useReducedMotion();
  const target = Number(value) || 0;
  const [display, setDisplay] = useState(target);
  const previous = useRef(target);

  useEffect(() => {
    const from = previous.current;
    previous.current = target;
    if (reducedMotion || from === target) {
      setDisplay(target);
      return undefined;
    }
    const controls = animate(from, target, {
      duration: 0.6,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (latest) => setDisplay(latest),
    });
    return () => controls.stop();
  }, [reducedMotion, target]);

  const rounded = Number.isInteger(target) ? Math.round(display) : display;
  return (
    <span className="orc-animated-number">
      <span aria-hidden="true">{format(rounded)}</span>
      <span className="orc-visually-hidden">{format(target)}</span>
    </span>
  );
}
