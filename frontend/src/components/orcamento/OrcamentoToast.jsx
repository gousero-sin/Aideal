import React, { useEffect } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { CheckCircle2, X } from 'lucide-react';
import { springSoft } from './orcamentoMotion';

const TOAST_DURATION_MS = 4500;

// Confirmação discreta de sucesso; some sozinha e não rouba o foco.
export default function OrcamentoToast({ onDismiss, toast }) {
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(onDismiss, TOAST_DURATION_MS);
    return () => clearTimeout(timer);
  }, [onDismiss, toast]);

  return (
    <div aria-live="polite" className="orc-toast-region" role="status">
      <AnimatePresence>
        {toast && (
          <motion.div
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className="orc-toast"
            exit={{ opacity: 0, y: reducedMotion ? 0 : 12, transition: { duration: reducedMotion ? 0 : 0.16 } }}
            initial={{ opacity: 0, y: reducedMotion ? 0 : 18, scale: reducedMotion ? 1 : 0.96 }}
            key={toast.id}
            transition={reducedMotion ? { duration: 0 } : springSoft}
          >
            <CheckCircle2 aria-hidden="true" />
            <p>{toast.message}</p>
            <button aria-label="Dispensar aviso" className="orc-icon-btn orc-icon-btn--small" onClick={onDismiss} type="button"><X aria-hidden="true" /></button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
