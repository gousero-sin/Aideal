import { useEffect, useRef } from 'react';

const focusableSelector = 'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]';

// Vários diálogos podem estar abertos ao mesmo tempo (editor + confirmação): a rolagem do
// body só volta quando o último fecha. A compensação da barra evita salto lateral.
let scrollLocks = 0;
let savedBodyStyle = null;

function lockBodyScroll() {
  if (typeof document === 'undefined') return;
  scrollLocks += 1;
  if (scrollLocks > 1) return;
  const { body, documentElement } = document;
  const scrollbar = window.innerWidth - documentElement.clientWidth;
  savedBodyStyle = { overflow: body.style.overflow, paddingRight: body.style.paddingRight };
  body.style.overflow = 'hidden';
  if (scrollbar > 0) body.style.paddingRight = `${scrollbar}px`;
  body.dataset.orcModalOpen = 'true';
}

function unlockBodyScroll() {
  if (typeof document === 'undefined' || scrollLocks === 0) return;
  scrollLocks -= 1;
  if (scrollLocks > 0) return;
  const { body } = document;
  body.style.overflow = savedBodyStyle?.overflow ?? '';
  body.style.paddingRight = savedBodyStyle?.paddingRight ?? '';
  delete body.dataset.orcModalOpen;
  savedBodyStyle = null;
}

/**
 * Foco preso no diálogo, Esc fecha (exceto durante envio), foco volta ao acionador e a
 * página por trás não rola. Para fechar ao clicar fora, use `closeOnBackdrop` no overlay.
 */
export default function useOrcamentoDialog({ busy, initialFocusRef, onClose }) {
  const dialogRef = useRef(null);
  const latest = useRef({ busy, onClose });
  latest.current = { busy, onClose };

  useEffect(() => {
    const previous = document.activeElement;
    lockBodyScroll();
    (initialFocusRef?.current || dialogRef.current)?.focus({ preventScroll: true });
    const handleKey = (event) => {
      const dialog = dialogRef.current;
      if (!dialog) return;
      // Só o diálogo mais recente (o último no DOM) reage ao teclado.
      const layers = document.querySelectorAll('[data-orc-dialog-layer="true"]');
      if (layers.length && layers[layers.length - 1] !== dialog) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        if (!latest.current.busy) latest.current.onClose();
      }
      if (event.key !== 'Tab') return;
      const elements = [...dialog.querySelectorAll(focusableSelector)]
        .filter((element) => element.getClientRects().length > 0);
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (!first) {
        event.preventDefault();
        dialog.focus();
      } else if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('keydown', handleKey);
      unlockBodyScroll();
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [initialFocusRef]);

  return dialogRef;
}

// Clique direto na camada (fora da janela) fecha, a menos que esteja enviando.
export const closeOnBackdrop = (busy, onClose) => (event) => {
  if (event.target === event.currentTarget && !busy) onClose();
};
