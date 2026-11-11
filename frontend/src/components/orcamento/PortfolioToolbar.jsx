import React, { useId } from 'react';
import { LayoutGroup, motion, useReducedMotion } from 'framer-motion';
import { ArrowDownUp, Search, X } from 'lucide-react';
import { FILTROS_CARTEIRA, ORDENACOES_CARTEIRA } from '../orcamentoModel';
import { springSoft } from './orcamentoMotion';

export default function PortfolioToolbar({ counts, filter, onFilter, onOrder, onQuery, order, query }) {
  const reducedMotion = useReducedMotion();
  const groupId = useId();
  return (
    <div className="orc-toolbar" role="search">
      <label className="orc-search">
        <Search aria-hidden="true" />
        <span className="orc-visually-hidden">Buscar orçamentos</span>
        <input
          autoComplete="off"
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Buscar por código ou contratante"
          type="search"
          value={query}
        />
        {query && (
          <button aria-label="Limpar busca" className="orc-search__clear" onClick={() => onQuery('')} type="button"><X aria-hidden="true" /></button>
        )}
      </label>
      <LayoutGroup id={groupId}>
        <div aria-label="Filtrar por situação" className="orc-filter-chips" role="group">
          {FILTROS_CARTEIRA.filter(({ value }) => value === 'todos' || value === filter || counts[value] > 0).map(({ value, label }) => {
            const active = filter === value;
            return (
              <button aria-pressed={active} className="orc-filter-chip" key={value} onClick={() => onFilter(value)} type="button">
                {active && <motion.span className="orc-filter-chip__pill" layoutId="orc-filter-pill" transition={reducedMotion ? { duration: 0 } : springSoft} />}
                <span className="orc-filter-chip__label">{label}</span>
                <span className="orc-filter-chip__count">{counts[value] ?? 0}</span>
              </button>
            );
          })}
        </div>
      </LayoutGroup>
      <label className="orc-sort">
        <ArrowDownUp aria-hidden="true" />
        <span className="orc-visually-hidden">Ordenar por</span>
        <select onChange={(event) => onOrder(event.target.value)} value={order}>
          {ORDENACOES_CARTEIRA.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
    </div>
  );
}
