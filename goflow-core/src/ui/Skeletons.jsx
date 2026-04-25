import React from 'react';

const classNames = (...names) => names.filter(Boolean).join(' ');

export const SkeletonBlock = ({ as: Component = 'div', className = '', style = {}, ...rest }) => (
  <Component
    aria-hidden="true"
    className={classNames('goflow-skeleton', className)}
    style={style}
    {...rest}
  />
);

export const SkeletonText = ({ className = '', style = {}, ...rest }) => (
  <SkeletonBlock
    className={classNames('goflow-skeleton-text', className)}
    style={style}
    {...rest}
  />
);

export const SkeletonCircle = ({ size = 40, className = '', style = {}, ...rest }) => (
  <SkeletonBlock
    className={classNames('goflow-skeleton-circle', className)}
    style={{ width: size, height: size, ...style }}
    {...rest}
  />
);

export const SkeletonChart = ({ className = '', height = 200, style = {}, ...rest }) => (
  <SkeletonBlock
    className={classNames('goflow-skeleton-chart', className)}
    style={{ height, ...style }}
    {...rest}
  />
);
