import React, { useId, useMemo, useState } from 'react';
import { ChevronDown, Search, SlidersHorizontal, X } from 'lucide-react';
import { MESES_LABEL, formatNumber, mergeCurrentYear, toggleValue } from './financialPanelUtils';

const getDefaultFilterOpen = () => {
  if (typeof window === 'undefined') return true;
  return !window.matchMedia('(max-width: 680px)').matches;
};

export function FilterDock({
  title,
  subtitle,
  activeCount,
  activeItems = [],
  onClear,
  clearDisabled,
  children,
}) {
  const bodyId = useId();
  const [open, setOpen] = useState(getDefaultFilterOpen);
  const visibleItems = activeItems.slice(0, 10);
  const hiddenCount = Math.max(activeItems.length - visibleItems.length, 0);

  return (
    <section className={`aideal-filter-shell ${open ? 'is-open' : ''}`}>
      <div className="aideal-filter-bar">
        <div className="aideal-filter-title">
          <SlidersHorizontal size={17} aria-hidden="true" />
          <div>
            <h3>{title}</h3>
            <p>{subtitle}</p>
          </div>
        </div>
        <div className="aideal-filter-actions">
          <span className={activeCount > 0 ? 'is-active' : ''}>
            {activeCount > 0 ? `${formatNumber(activeCount)} filtro(s)` : 'Todos os dados'}
          </span>
          <button type="button" onClick={onClear} disabled={clearDisabled}>
            Limpar tudo
          </button>
          <button
            type="button"
            className="aideal-filter-toggle"
            onClick={() => setOpen((current) => !current)}
            aria-expanded={open}
            aria-controls={bodyId}
          >
            {open ? 'Ocultar' : 'Mostrar'}
            <ChevronDown size={15} aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="aideal-filter-summary" aria-label="Filtros ativos">
        {visibleItems.length === 0 ? (
          <span>Sem recortes ativos. Os gráficos mostram todos os dados disponíveis no período.</span>
        ) : (
          visibleItems.map((item) => (
            <em key={`${item.key}-${item.value}`} title={item.text}>
              {item.text}
            </em>
          ))
        )}
        {hiddenCount > 0 && <em>+{formatNumber(hiddenCount)} selecionado(s)</em>}
      </div>

      {open && (
        <div id={bodyId} className="aideal-filter-body">
          <section className="aideal-slicer-dock">{children}</section>
        </div>
      )}
    </section>
  );
}

export function YearSelect({ anos, value, onChange }) {
  const options = mergeCurrentYear(anos, value);
  return (
    <label className="aideal-year-select">
      Ano
      <select value={value || ''} onChange={(event) => onChange(event.target.value)}>
        {options.map((ano) => (
          <option key={ano} value={ano}>
            {ano}
          </option>
        ))}
      </select>
    </label>
  );
}

export function MonthSlicer({ available, selected, onChange }) {
  const selectedSet = new Set(selected || []);
  const selectedCount = selected?.length || 0;
  const availableCount = available?.length || 0;
  return (
    <div className="aideal-slicer-card aideal-slicer-months">
      <div className="aideal-slicer-heading">
        <strong>
          Meses
          <span>{selectedCount > 0 ? `${selectedCount}/${availableCount}` : formatNumber(availableCount)}</span>
        </strong>
        <button type="button" onClick={() => onChange([])} disabled={!selected?.length}>
          Todos
        </button>
      </div>
      <div className="aideal-slicer-chip-grid">
        {(available || []).map((mes) => {
          const isSelected = selectedSet.has(mes);
          return (
            <button
              key={mes}
              type="button"
              className={`aideal-slicer-chip ${isSelected ? 'is-selected' : ''}`}
              onClick={() => onChange(toggleValue(selected || [], mes).sort((a, b) => a - b))}
              aria-pressed={isSelected}
            >
              {MESES_LABEL[mes - 1]}
            </button>
          );
        })}
        {(!available || available.length === 0) && (
          <span className="aideal-slicer-empty">Sem meses salvos</span>
        )}
      </div>
    </div>
  );
}

export function SearchableSlicer({ title, options, selected, onChange }) {
  const [query, setQuery] = useState('');
  const selectedSet = new Set(selected || []);
  const selectedCount = selected?.length || 0;
  const totalOptions = Array.isArray(options) ? options.length : 0;
  const filteredOptions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const source = Array.isArray(options) ? options : [];
    if (!normalized) return source.slice(0, 80);
    return source
      .filter((option) => String(option.label || option.value).toLowerCase().includes(normalized))
      .slice(0, 80);
  }, [options, query]);

  return (
    <div className="aideal-slicer-card">
      <div className="aideal-slicer-heading">
        <strong>
          {title}
          <span>{selectedCount > 0 ? `${selectedCount}/${totalOptions}` : formatNumber(totalOptions)}</span>
        </strong>
        <button type="button" onClick={() => onChange([])} disabled={!selected?.length}>
          Limpar
        </button>
      </div>
      <label className="aideal-slicer-search">
        <Search size={14} aria-hidden="true" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar"
          aria-label={`Buscar em ${title}`}
        />
      </label>
      <div className="aideal-slicer-list">
        {filteredOptions.map((option) => {
          const value = option.value;
          const isSelected = selectedSet.has(value);
          return (
            <button
              key={value}
              type="button"
              className={`aideal-slicer-option ${isSelected ? 'is-selected' : ''}`}
              onClick={() => onChange(toggleValue(selected || [], value))}
              aria-pressed={isSelected}
              title={option.label}
            >
              <span>{option.label}</span>
              <em>{formatNumber(option.total)}</em>
            </button>
          );
        })}
        {filteredOptions.length === 0 && (
          <span className="aideal-slicer-empty">Nenhuma opção encontrada</span>
        )}
      </div>
      {selected?.length > 0 && (
        <div className="aideal-selected-strip">
          {selected.slice(0, 8).map((value) => (
            <button key={value} type="button" onClick={() => onChange(toggleValue(selected, value))}>
              <span>{value}</span>
              <X size={12} aria-hidden="true" />
            </button>
          ))}
          {selected.length > 8 && <span>+{formatNumber(selected.length - 8)}</span>}
        </div>
      )}
    </div>
  );
}
