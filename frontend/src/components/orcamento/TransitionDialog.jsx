import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, GitCommitHorizontal, Loader2, X } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import useOrcamentoDialog, { closeOnBackdrop } from './useOrcamentoDialog';
import { backdropMotion, windowMotion } from './orcamentoMotion';
import { GoFlowWindow } from '../goflow-window';

export default function TransitionDialog({ busy, label, onCancel, onConfirm, revision, serverError }) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const textareaRef = useRef(null);
  const serverErrorRef = useRef(null);

  const reducedMotion = useReducedMotion();
  const dialogRef = useOrcamentoDialog({ busy, initialFocusRef: textareaRef, onClose: onCancel });

  // O erro do servidor aparece só aqui (não na página) e recebe foco para ser anunciado.
  useEffect(() => {
    if (serverError && !busy) serverErrorRef.current?.focus({ preventScroll: false });
  }, [serverError, busy]);

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!reason.trim()) {
      setError('Registre o motivo da mudança para preservar a trilha de auditoria.');
      textareaRef.current?.focus();
      return;
    }
    onConfirm(reason.trim());
  };

  return (
    <motion.div
      {...backdropMotion(reducedMotion)}
      className="orc-dialog-layer"
      data-orc-dialog-layer="true"
      onClick={closeOnBackdrop(busy, onCancel)}
      ref={dialogRef}
      tabIndex={-1}
    >
      <GoFlowWindow
        actions={(
          <button aria-label="Fechar" className="orc-icon-btn" disabled={busy} onClick={onCancel} type="button">
            <X aria-hidden="true" />
          </button>
        )}
        aria-labelledby="orc-transition-title"
        aria-modal="true"
        className="orc-transition-dialog"
        eyebrow={`Revisão ${revision.numero}`}
        icon={GitCommitHorizontal}
        motionProps={windowMotion(reducedMotion)}
        role="dialog"
        title="Alterar situação"
        titleAs="h2"
      >
        <form onSubmit={handleSubmit}>
          {serverError && <p className="orc-validation-error" ref={serverErrorRef} role="alert" tabIndex={-1}>{serverError}</p>}
          <p id="orc-transition-title">Mover de <strong>{revision.situacaoLabel}</strong> para <strong>{label}</strong>.</p>
          <label className="orc-field">
            <span>Motivo da mudança</span>
            <textarea
              aria-invalid={Boolean(error)}
              disabled={busy}
              onChange={(event) => { setReason(event.target.value); setError(''); }}
              ref={textareaRef}
              rows="4"
              value={reason}
            />
            {error && <small role="alert">{error}</small>}
          </label>
          <div className="orc-button-row">
            <button className="orc-btn" disabled={busy} onClick={onCancel} type="button">Cancelar</button>
            <button className="orc-btn orc-btn--primary" disabled={busy} type="submit">
              {busy ? <Loader2 className="orc-spin" aria-hidden="true" /> : null}Confirmar {!busy && <ArrowRight aria-hidden="true" />}
            </button>
          </div>
        </form>
      </GoFlowWindow>
    </motion.div>
  );
}
