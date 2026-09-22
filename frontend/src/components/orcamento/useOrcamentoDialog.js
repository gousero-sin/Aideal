import { useEffect, useRef } from 'react';

const focusableSelector = 'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]';

export default function useOrcamentoDialog({ busy, initialFocusRef, onClose }) {
  const dialogRef = useRef(null);
  const latest = useRef({ busy, onClose });
  latest.current = { busy, onClose };

  useEffect(() => {
    const previous = document.activeElement;
    initialFocusRef.current?.focus({ preventScroll: true });
    const handleKey = (event) => {
      const dialog = dialogRef.current;
      if (!dialog) return;
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
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [initialFocusRef]);

  return dialogRef;
}
