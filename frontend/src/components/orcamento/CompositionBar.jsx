import React, { useMemo } from 'react';
import { composicaoDoPreco } from '../orcamentoModel';

const formatMoney = (value) => Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const formatShare = (share) => `${(share * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`;

/**
 * Faixa de composição do preço: custos diretos, indiretos, lucro e impostos na proporção em
 * que formam o preço de faturamento. `legend` acrescenta os valores de cada parte.
 * @param {{ summary: object, legend?: boolean, className?: string }} props
 */
export default function CompositionBar({ className = '', legend = false, summary }) {
  const partes = useMemo(() => composicaoDoPreco(summary), [summary]);
  if (!partes.length) {
    return <div className={`orc-comp orc-comp--empty ${className}`}><span className="orc-comp__track" /><span className="orc-comp__hint">Sem preço calculado</span></div>;
  }
  const descricao = partes.map(({ label, share }) => `${label} ${formatShare(share)}`).join(', ');
  return (
    <div className={`orc-comp ${className}`}>
      <span aria-label={`Composição do preço: ${descricao}`} className="orc-comp__track" role="img">
        {partes.map(({ key, label, share, valor }) => (
          <span className="orc-comp__part" data-part={key} key={key} style={{ flexGrow: share }} title={`${label}: ${formatMoney(valor)} (${formatShare(share)})`} />
        ))}
      </span>
      {legend && (
        <dl className="orc-comp__legend">
          {partes.map(({ key, label, share, valor }) => (
            <div data-part={key} key={key}>
              <dt>{label}<span>{formatShare(share)}</span></dt>
              <dd>{formatMoney(valor)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
