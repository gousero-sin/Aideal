import React, { useId, useRef } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { CircleHelp, Loader2, X } from 'lucide-react';
import useOrcamentoDialog, { closeOnBackdrop } from './useOrcamentoDialog';
import { backdropMotion, windowMotion } from './orcamentoMotion';
import { GoFlowWindow } from '../goflow-window';

/**
 * Confirmação curta e reutilizável. Renderize dentro de <AnimatePresence>.
 * `tone="danger"` destaca ações que descartam dados.
 */
export default function ConfirmDialog({
  busy = false,
  cancelLabel = 'Cancelar',
  children,
  confirmLabel = 'Confirmar',
  error,
  eyebrow,
  icon = CircleHelp,
  onCancel,
  onConfirm,
  title,
  tone = 'default',
}) {
  const reducedMotion = useReducedMotion();
  const confirmRef = useRef(null);
  const dialogRef = useOrcamentoDialog({ busy, initialFocusRef: confirmRef, onClose: onCancel });
  const id = useId();
  const descriptionId = `${id}-description`;

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
        aria-describedby={descriptionId}
        aria-label={title}
        aria-modal="true"
        className="orc-transition-dialog orc-confirm-dialog"
        data-tone={tone}
        eyebrow={eyebrow}
        icon={icon}
        motionProps={windowMotion(reducedMotion)}
        role="dialog"
        title={title}
        titleAs="h2"
      >
        <div className="orc-confirm-body" id={descriptionId}>{children}</div>
        {error && <p className="orc-validation-error" role="alert">{error}</p>}
        <div className="orc-button-row">
          <button className="orc-btn" disabled={busy} onClick={onCancel} type="button">{cancelLabel}</button>
          <button
            className={`orc-btn ${tone === 'danger' ? 'orc-btn--danger' : 'orc-btn--primary'}`}
            disabled={busy}
            onClick={onConfirm}
            ref={confirmRef}
            type="button"
          >
            {busy && <Loader2 className="orc-spin" aria-hidden="true" />}{confirmLabel}
          </button>
        </div>
      </GoFlowWindow>
    </motion.div>
  );
}
