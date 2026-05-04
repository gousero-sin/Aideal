import React from 'react';
import { ArrowRight, BarChart3, WalletCards } from 'lucide-react';

export default function FlowSelector({ onSelect }) {
  const cards = [
      {
        key: 'dre',
        icon: <BarChart3 size={24} aria-hidden="true" />,
        title: 'Fluxo DRE',
        description:
        'Importa planilha mensal bruta, valida a estrutura e prepara a geração do template AIDEAL.',
        cta: 'Selecionar DRE',
      },
    {
      key: 'fluxo_caixa',
      icon: <WalletCards size={24} aria-hidden="true" />,
      title: 'Fluxo de Caixa',
      description:
        'Importa lote bancário, valida consistência e prepara consolidação por origem.',
      cta: 'Selecionar Fluxo',
    },
  ];

  return (
    <section className="aideal-grid-2">
      {cards.map((card) => (
        <article key={card.key} className="aideal-card aideal-flow-card">
          <div className="aideal-card-icon">
            {card.icon}
          </div>

          <h2>{card.title}</h2>

          <p>{card.description}</p>

          <button className="aideal-action aideal-action-primary" onClick={() => onSelect(card.key)}>
            <span>{card.cta}</span>
            <ArrowRight size={16} aria-hidden="true" />
          </button>
        </article>
      ))}
    </section>
  );
}
