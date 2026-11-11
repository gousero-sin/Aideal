import React, { useEffect, useRef } from 'react';
import { AlertCircle, CheckCircle2, Download, Loader2, Save } from 'lucide-react';
import { GoFlowWindow } from '../../goflow-window';
import AnimatedValue from './AnimatedValue';
import { pluralize } from './editorState';

const EXPORT_FORMATS = ['docx', 'pdf'];

/**
 * Rodapé fixo do editor: estado das alterações, preço total, erro do servidor (sempre à vista,
 * pois o rodapé é sticky) e ações. Exportar usa a versão salva, então fica bloqueado enquanto
 * houver alterações pendentes.
 */
export default function EditorFooter({
  busy,
  canEdit,
  dirty,
  exporting,
  issueCount,
  onClose,
  onExport,
  saveButtonRef,
  serverError,
  total,
  totalLabel,
}) {
  const errorRef = useRef(null);
  useEffect(() => {
    if (serverError) errorRef.current?.focus({ preventScroll: true });
  }, [serverError]);
  const exportBlocked = dirty || Boolean(exporting);
  const exportHint = dirty ? 'Salve a revisão para exportar com as alterações.' : undefined;

  return (
    <GoFlowWindow className="orc-editor-footer" title="Finalizar edição">
      {serverError && (
        <div className="orc-validation-error orc-editor-footer__error" ref={errorRef} role="alert" tabIndex={-1}>
          <AlertCircle aria-hidden="true" /><span>{serverError}</span>
        </div>
      )}
      <div className="orc-editor-footer__row">
        <div className="orc-editor-footer__status">
          {canEdit && (dirty
            ? <span className="orc-save-state" data-state="dirty"><AlertCircle aria-hidden="true" />Alterações não salvas</span>
            : <span className="orc-save-state" data-state="clean"><CheckCircle2 aria-hidden="true" />Sem alterações pendentes</span>)}
          {issueCount > 0 && <span className="orc-save-state" data-state="invalid">{pluralize(issueCount, 'pendência', 'pendências')} para revisar</span>}
          <span className="orc-editor-footer__total"><small>{totalLabel}</small><strong><AnimatedValue value={total} /></strong></span>
        </div>
        <p>{canEdit ? 'Revise as premissas antes de salvar.' : 'Esta revisão está disponível somente para consulta.'}{exportHint && ` ${exportHint}`}</p>
        <div className="orc-button-row">
          <button className="orc-btn" disabled={busy} onClick={onClose} type="button">Fechar</button>
          {EXPORT_FORMATS.map((format) => {
            const running = exporting === format;
            return (
              <button
                aria-busy={running || undefined}
                className="orc-btn"
                disabled={exportBlocked}
                key={format}
                onClick={() => onExport(format)}
                title={exportHint}
                type="button"
              >
                {running ? <Loader2 aria-hidden="true" className="orc-spin" /> : <Download aria-hidden="true" />}
                Exportar {format.toUpperCase()} salvo
              </button>
            );
          })}
          {canEdit && (
            <button className="orc-btn orc-btn--primary" disabled={busy} ref={saveButtonRef} type="submit">
              {busy ? <Loader2 aria-hidden="true" className="orc-spin" /> : <Save aria-hidden="true" />} Salvar revisão
            </button>
          )}
        </div>
      </div>
    </GoFlowWindow>
  );
}
