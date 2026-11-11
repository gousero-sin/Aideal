import React, { useId } from 'react';
import { LayoutGroup, motion, useReducedMotion } from 'framer-motion';
import { BookOpenCheck } from 'lucide-react';
import { GoFlowWindow } from '../../goflow-window';
import { springSoft } from '../orcamentoMotion';
import { pluralize } from './editorState';

const issuesLabel = (count) => pluralize(count, 'pendência', 'pendências');

/** Navegação lateral por seções. Botões: a navegação não altera o hash da página. */
export function EditorSectionNav({ active, issues, items, onNavigate }) {
  const reducedMotion = useReducedMotion();
  // layoutId por instância: dois editores (ou um remanescente em saída) não disputam o indicador.
  const groupId = useId();
  return (
    <GoFlowWindow as="nav" aria-label="Seções do orçamento" className="orc-editor-nav" eyebrow="Seções" icon={BookOpenCheck} title="Formação de preços">
      <LayoutGroup id={groupId}>
        {items.map((item) => {
          const current = active === item.id;
          const count = issues[item.id] || 0;
          return (
            <button
              aria-current={current ? 'location' : undefined}
              aria-describedby={count ? `${groupId}-${item.id}-issues` : undefined}
              className="orc-editor-nav__item"
              key={item.id}
              onClick={() => onNavigate(item.id)}
              type="button"
            >
              {current && <motion.span aria-hidden="true" className="orc-nav-indicator" layoutId="orc-active-section" transition={reducedMotion ? { duration: 0 } : springSoft} />}
              <span className="orc-nav-label">{item.title}</span>
              {count > 0 && <span className="orc-nav-badge" id={`${groupId}-${item.id}-issues`} title={issuesLabel(count)}><span aria-hidden="true">{count}</span><span className="orc-visually-hidden">{issuesLabel(count)}</span></span>}
            </button>
          );
        })}
      </LayoutGroup>
    </GoFlowWindow>
  );
}

/** Seletor compacto de seção para telas estreitas (rótulo usado nos testes e2e). */
export function MobileSectionNav({ active, issues, items, onNavigate }) {
  return (
    <label className="orc-mobile-nav">
      <span>Seção do orçamento</span>
      <select value={active} onChange={(event) => onNavigate(event.target.value)}>
        {items.map((item) => {
          const count = issues[item.id] || 0;
          return <option key={item.id} value={item.id}>{count ? `${item.title} (${issuesLabel(count)})` : item.title}</option>;
        })}
      </select>
    </label>
  );
}
