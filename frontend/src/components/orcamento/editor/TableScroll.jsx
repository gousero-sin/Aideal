import React, { useLayoutEffect, useRef, useState } from 'react';

/**
 * Rolagem horizontal da tabela com barra superior espelhada.
 * A barra de cima só aparece quando a tabela é mais larga que a área visível e acompanha a
 * largura real do conteúdo (ResizeObserver), para as duas barras chegarem juntas ao fim.
 * `.orc-table-scroll`, `.orc-table-scroll-top` e `data-scroll-key` são usados pelo editor para
 * preservar a rolagem ao minimizar e pelos testes e2e.
 */
export default function TableScroll({ children, label, scrollKey }) {
  const bottom = useRef(null);
  const top = useRef(null);
  const [metrics, setMetrics] = useState({ overflow: false, width: 0 });

  useLayoutEffect(() => {
    const container = bottom.current;
    const table = container?.querySelector('table');
    if (!container || !table) return undefined;
    const measure = () => {
      const gutter = container.offsetWidth - container.clientWidth;
      const width = container.scrollWidth + gutter;
      const overflow = container.scrollWidth > container.clientWidth + 1;
      setMetrics((current) => (
        current.width === width && current.overflow === overflow ? current : { overflow, width }
      ));
    };
    measure();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(measure);
    observer.observe(table);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useLayoutEffect(() => {
    if (metrics.overflow && top.current && bottom.current) top.current.scrollLeft = bottom.current.scrollLeft;
  }, [metrics.overflow]);

  const syncFromTop = () => {
    if (bottom.current && top.current && bottom.current.scrollLeft !== top.current.scrollLeft) {
      bottom.current.scrollLeft = top.current.scrollLeft;
    }
  };
  const syncFromBottom = () => {
    if (bottom.current && top.current && top.current.scrollLeft !== bottom.current.scrollLeft) {
      top.current.scrollLeft = bottom.current.scrollLeft;
    }
  };

  return (
    <>
      <div
        aria-label={`Rolagem superior de ${label}`}
        className="orc-table-scroll-top"
        hidden={!metrics.overflow}
        onScroll={syncFromTop}
        ref={top}
        tabIndex={metrics.overflow ? 0 : -1}
      >
        <div style={{ width: metrics.width, height: 1 }} />
      </div>
      <div
        aria-label={`${label}, tabela rolável`}
        className={`orc-table-scroll ${metrics.overflow ? 'has-overflow' : ''}`}
        data-scroll-key={scrollKey}
        onScroll={syncFromBottom}
        ref={bottom}
        role="region"
        tabIndex={0}
      >
        {children}
      </div>
    </>
  );
}
