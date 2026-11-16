import React, { useId, useRef } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { X } from 'lucide-react';
import useOrcamentoDialog, { closeOnBackdrop } from './useOrcamentoDialog';
import { backdropMotion, windowMotion } from './orcamentoMotion';
import { GoFlowWindow } from '../goflow-window';

/**
 * Diálogo de trabalho (formulários longos): cabeçalho fixo, corpo rolável e rodapé de ações.
 * Renderize dentro de <AnimatePresence>. Clique fora e Esc fecham, exceto durante envio.
 */
export default function OrcamentoDialog({
  busy = false, children, className = '', description, footer, icon, onClose, title,
}) {
  const reducedMotion = useReducedMotion();
  const closeRef = useRef(null);
  const dialogRef = useOrcamentoDialog({ busy, initialFocusRef: closeRef, onClose });
  const descriptionId = useId();
  return (
    <motion.div
      {...backdropMotion(reducedMotion)}
      className="orc-dialog-layer"
      data-orc-dialog-layer="true"
      onMouseDown={closeOnBackdrop(busy, onClose)}
      ref={dialogRef}
      tabIndex={-1}
    >
      <GoFlowWindow
        actions={<button aria-label="Fechar" className="orc-icon-btn" disabled={busy} onClick={onClose} ref={closeRef} type="button"><X aria-hidden="true" /></button>}
        aria-describedby={description ? descriptionId : undefined}
        aria-label={title}
        aria-modal="true"
        className={`orc-work-dialog ${className}`}
        icon={icon}
        motionProps={windowMotion(reducedMotion)}
        role="dialog"
        title={title}
        titleAs="h2"
      >
        {description && <p className="orc-work-dialog__description" id={descriptionId}>{description}</p>}
        <div className="orc-work-dialog__body">{children}</div>
        {footer && <div className="orc-work-dialog__footer">{footer}</div>}
      </GoFlowWindow>
    </motion.div>
  );
}
