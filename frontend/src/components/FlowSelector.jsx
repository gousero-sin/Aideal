import React from 'react';

export default function FlowSelector({ onSelect }) {
  const cards = [
      {
        key: 'dre',
        icon: 'DRE',
        title: 'Fluxo DRE',
        description:
        'Importa planilha mensal bruta, valida a estrutura e prepara a geração do template AIDEAL.',
        cta: 'Selecionar DRE',
      },
    {
      key: 'fluxo_caixa',
      icon: 'FC',
      title: 'Fluxo de Caixa',
      description:
        'Importa lote bancário, valida consistência e prepara consolidação por origem.',
      cta: 'Selecionar Fluxo',
    },
  ];

  return (
    <section className="aideal-grid-2">
      {cards.map((card) => (
        <article key={card.key} className="aideal-card" style={{ padding: '18px' }}>
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '12px',
              background: 'rgba(22, 135, 224, 0.12)',
              color: 'var(--aideal-primary-dark)',
              fontWeight: 700,
              display: 'grid',
              placeItems: 'center',
              marginBottom: '12px',
            }}
          >
            {card.icon}
          </div>

          <h2 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--aideal-primary-dark)' }}>
            {card.title}
          </h2>

          <p style={{ margin: '8px 0 14px', color: 'var(--aideal-text-soft)', fontSize: '0.9rem' }}>
            {card.description}
          </p>

          <button className="aideal-action aideal-action-primary" onClick={() => onSelect(card.key)}>
            {card.cta}
          </button>
        </article>
      ))}
    </section>
  );
}
