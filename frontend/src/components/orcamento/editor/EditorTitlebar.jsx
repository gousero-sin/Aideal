import React from 'react';
import { FileText, LockKeyhole, Maximize2, Minimize2, Minus, X } from 'lucide-react';
import { GoFlowWindow } from '../../goflow-window';

export default function EditorTitlebar({
  budget,
  busy,
  canEdit,
  closeButtonRef,
  dirty,
  layoutKey,
  maximized,
  minimized,
  onClose,
  onToggleMaximized,
  onToggleMinimized,
  reducedMotion,
  revision,
}) {
  return (
    <GoFlowWindow
      actions={(
        <div className="orc-window-controls">
          <button
            aria-label={minimized ? 'Restaurar editor' : 'Minimizar editor'}
            className="orc-icon-btn"
            onClick={onToggleMinimized}
            type="button"
          >
            <Minus aria-hidden="true" />
          </button>
          <button
            aria-label={maximized ? 'Restaurar tamanho do editor' : 'Maximizar editor'}
            className="orc-icon-btn"
            disabled={minimized}
            onClick={onToggleMaximized}
            type="button"
          >
            {maximized ? <Minimize2 aria-hidden="true" /> : <Maximize2 aria-hidden="true" />}
          </button>
          <button
            aria-label="Fechar editor"
            className="orc-icon-btn orc-icon-btn--close"
            disabled={busy}
            onClick={onClose}
            ref={closeButtonRef}
            type="button"
          >
            <X aria-hidden="true" />
          </button>
        </div>
      )}
      className="orc-editor-titlebar"
      eyebrow={`${budget.codigo.replace(/-R\d+$/, '')}-R${revision.numero}`}
      icon={canEdit ? FileText : LockKeyhole}
      // Mantém o conteúdo da barra sem distorção enquanto a janela muda de tamanho.
      motionProps={reducedMotion ? undefined : { layout: 'position', layoutDependency: layoutKey }}
      title={<span className="orc-editor-titlebar__name" title={budget.contratante}>{budget.contratante}</span>}
      titleAs="h2"
    >
      <p id="orc-editor-mode">
        {canEdit
          ? 'Composição de preços. As alterações serão gravadas apenas nesta revisão.'
          : 'Histórico em modo somente leitura. Esta revisão permanece preservada.'}
        {dirty && <span className="orc-dirty-dot" title="Alterações não salvas"><span className="orc-visually-hidden"> Há alterações não salvas.</span></span>}
      </p>
    </GoFlowWindow>
  );
}
