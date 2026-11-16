import React, { useMemo } from 'react';
import { Plus, SlidersHorizontal } from 'lucide-react';
import AnimatedNumber from './AnimatedNumber';
import { formatarValorCompacto, funilCarteira } from '../orcamentoModel';

const formatMoney = (value) => Number(value || 0).toLocaleString('pt-BR', {
  style: 'currency', currency: 'BRL', maximumFractionDigits: 0,
});
const plural = (count, one, many) => `${count.toLocaleString('pt-BR')} ${count === 1 ? one : many}`;

/**
 * Cabeçalho da carteira: título, ações e o funil por etapa. Cada etapa é um filtro; a largura
 * cresce com o valor somado da etapa (de forma atenuada, para nenhuma etapa sumir).
 */
export default function PortfolioHeader({ budgets, canEdit, filter, onCatalog, onCreate, onFilter, summary }) {
  const funil = useMemo(() => funilCarteira(budgets), [budgets]);
  return (
    <header className="orc-head">
      <div className="orc-head__top">
        <div className="orc-head__title">
          <h2>Central de Orçamentos</h2>
          <p>
            {summary.total === 0 ? 'Nenhum orçamento na carteira ainda.' : (
              <>
                {plural(summary.total, 'orçamento', 'orçamentos')}, <strong><AnimatedNumber format={formatMoney} value={summary.totalFaturamento} /></strong> em preço de faturamento
              </>
            )}
          </p>
        </div>
        {canEdit && (
          <div className="orc-head__actions">
            <button className="orc-btn" onClick={onCatalog} type="button"><SlidersHorizontal aria-hidden="true" /> Cadastros</button>
            <button className="orc-btn orc-btn--primary" onClick={onCreate} type="button"><Plus aria-hidden="true" /> Novo orçamento</button>
          </div>
        )}
      </div>
      {summary.total > 0 && (
        <div aria-label="Etapas da carteira" className="orc-funnel" role="group">
          {funil.map(({ filtro, label, quantidade, share, valor }) => {
            const active = filter === filtro;
            return (
              <button
                aria-pressed={active}
                className="orc-funnel__stage"
                data-stage={filtro}
                key={filtro}
                onClick={() => onFilter(active ? 'todos' : filtro)}
                style={{ flexGrow: 1 + share * 3 }}
                title={active ? 'Mostrar todos os orçamentos' : `Filtrar: ${label}`}
                type="button"
              >
                <span className="orc-funnel__label">{label}</span>
                <span className="orc-funnel__value">{formatarValorCompacto(valor)}</span>
                <span className="orc-funnel__count">{plural(quantidade, 'orçamento', 'orçamentos')}</span>
              </button>
            );
          })}
        </div>
      )}
    </header>
  );
}
