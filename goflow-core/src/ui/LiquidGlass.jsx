import React from 'react';

const classNames = (...names) => names.filter(Boolean).join(' ');

export const LiquidGlassSurface = ({
  as: Component = 'div',
  children,
  className = '',
  variant = 'default',
  interactive = false,
  style = {},
  ...rest
}) => {
  const variantClass = variant === 'soft'
    ? 'goflow-liquid-glass--soft'
    : variant === 'strong'
      ? 'goflow-liquid-glass--strong'
      : '';

  return (
    <Component
      className={classNames(
        'goflow-liquid-glass',
        variantClass,
        interactive && 'goflow-liquid-glass--interactive',
        className
      )}
      style={style}
      {...rest}
    >
      {children}
    </Component>
  );
};

export const LiquidGlassCard = ({ className = '', ...props }) => {
  return <LiquidGlassSurface className={classNames('goflow-liquid-card', className)} {...props} />;
};
