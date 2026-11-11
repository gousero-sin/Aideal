import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { pickActiveSection } from './editorState';

const SECTION_SELECTOR = '[id^="orc-section-"]';
// Durante a rolagem suave disparada pela navegação, a seção escolhida não pisca para as
// intermediárias.
const NAVIGATION_LOCK_MS = 700;

const readSections = (container) => {
  const top = container.getBoundingClientRect().top;
  return [...container.querySelectorAll(SECTION_SELECTOR)].map((element) => ({
    id: element.id,
    top: element.getBoundingClientRect().top - top,
  }));
};

/** Seção ativa na rolagem do formulário e navegação até uma seção. */
export function useActiveSection(containerRef, { enabled, initial, reducedMotion, watch }) {
  const [active, setActive] = useState(initial);
  const lockUntil = useRef(0);

  useEffect(() => {
    const container = containerRef.current;
    if (!enabled || !container) return undefined;
    let frame = 0;
    const update = () => {
      frame = 0;
      if (Date.now() < lockUntil.current) return;
      const id = pickActiveSection({
        sections: readSections(container),
        scrollTop: container.scrollTop,
        scrollHeight: container.scrollHeight,
        clientHeight: container.clientHeight,
      });
      if (id) setActive(id);
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    const release = () => { lockUntil.current = 0; schedule(); };
    container.addEventListener('scroll', schedule, { passive: true });
    container.addEventListener('scrollend', release);
    update();
    return () => {
      container.removeEventListener('scroll', schedule);
      container.removeEventListener('scrollend', release);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [containerRef, enabled, watch]);

  const navigateTo = useCallback((id) => {
    const section = document.getElementById(id);
    if (!section) return;
    setActive(id);
    lockUntil.current = Date.now() + (reducedMotion ? 0 : NAVIGATION_LOCK_MS);
    section.scrollIntoView({ behavior: reducedMotion ? 'instant' : 'smooth', block: 'start' });
  }, [reducedMotion]);

  return { active, navigateTo };
}

const ISSUE_SELECTOR = '[aria-invalid="true"], input:invalid, select:invalid, textarea:invalid';

/**
 * Pendências por seção depois da primeira tentativa de salvar: campos marcados pelo
 * validador do formulário, restrições nativas (mín./máx.) e avisos de validação.
 */
export function useSectionIssues(containerRef, { enabled }) {
  const [issues, setIssues] = useState({});
  useLayoutEffect(() => {
    const container = containerRef.current;
    const next = {};
    if (enabled && container) {
      container.querySelectorAll(SECTION_SELECTOR).forEach((section) => {
        const count = section.querySelectorAll(ISSUE_SELECTOR).length
          + section.querySelectorAll('.orc-validation-error').length;
        if (count) next[section.id] = count;
      });
    }
    setIssues((current) => (JSON.stringify(current) === JSON.stringify(next) ? current : next));
  });
  return issues;
}

export const firstIssueIn = (container) => container?.querySelector(`${ISSUE_SELECTOR}, .orc-validation-error`) || null;
