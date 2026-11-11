import React, { forwardRef } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

const joinClasses = (...classes) => classes.filter(Boolean).join(' ');

/**
 * Janela GoFlow. Para diálogos, anime a camada de fundo com `backdropMotion` e passe
 * `windowMotion` em `motionProps` aqui: assim só a janela escala, nunca o overlay.
 * `motionProps` também aceita `layout`, `layoutId` e `exit` (cartões em AnimatePresence).
 */
const GoFlowWindow = forwardRef(function GoFlowWindow({
  activationLabel,
  actions,
  as: Element = 'section',
  children,
  className,
  eyebrow,
  icon: Icon,
  interactive = false,
  motionIndex = 0,
  motionProps,
  onActivate,
  title,
  titleAs: TitleElement = 'h3',
  ...rest
}, ref) {
  const reducedMotion = useReducedMotion();
  const animated = interactive || Boolean(motionProps);
  const MotionElement = animated ? motion[Element] : Element;
  const interaction = interactive ? {
    initial: reducedMotion ? false : { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    whileHover: reducedMotion ? undefined : { y: -3 },
    whileTap: reducedMotion ? undefined : { scale: .995 },
    transition: { duration: reducedMotion ? 0 : .24, opacity: { delay: reducedMotion ? 0 : Math.min(motionIndex, 5) * .035 } },
  } : {};
  const handleClick = (event) => {
    rest.onClick?.(event);
    if (!interactive || event.defaultPrevented) return;
    onActivate?.(event);
  };

  return (
    <MotionElement
      {...interaction}
      {...motionProps}
      {...rest}
      ref={ref}
      className={joinClasses('goflow-window', interactive && 'goflow-window--interactive', className)}
      data-goflow-window="true"
      onClick={handleClick}
    >
      {interactive && (
        <button
          aria-label={activationLabel || title || 'Abrir janela'}
          className="goflow-window__activation"
          type="button"
        />
      )}
      {(title || eyebrow || actions) && (
        <header className="goflow-window__bar">
          <div className="goflow-window__identity">
            {Icon && <span className="goflow-window__icon"><Icon aria-hidden="true" /></span>}
            <div>
              {eyebrow && <span className="goflow-window__eyebrow">{eyebrow}</span>}
              {title && <TitleElement className="goflow-window__title">{title}</TitleElement>}
            </div>
          </div>
          {actions && <div className="goflow-window__actions">{actions}</div>}
        </header>
      )}
      <div className="goflow-window__content">{children}</div>
    </MotionElement>
  );
});

export default GoFlowWindow;
