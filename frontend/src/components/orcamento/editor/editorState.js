// Regras puras do editor de orçamento (sem React/DOM), testadas em
// src/components/orcamentoEditorState.test.js.

const sortKeys = (value) => {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === 'object') {
    return Object.keys(value).sort().reduce((acc, key) => {
      if (value[key] !== undefined) acc[key] = sortKeys(value[key]);
      return acc;
    }, {});
  }
  return value;
};

/** Serialização estável (ordem de chaves irrelevante) para comparar o formulário com o snapshot. */
export const serializeEditorForm = (form) => JSON.stringify(sortKeys(form ?? null));

export const isEditorDirty = (baseline, form) => baseline !== serializeEditorForm(form);

/**
 * Decide a nova linha de base quando o editor semeia dados sozinho (ex.: modelo HH padrão).
 * Só rebaseia se o formulário ainda estava limpo; alteração do usuário continua pendente.
 */
export const rebaseIfClean = (baseline, currentForm, seededForm) => (
  isEditorDirty(baseline, currentForm) ? baseline : serializeEditorForm(seededForm)
);

/**
 * Seção ativa da navegação a partir das posições das janelas.
 * `sections`: [{ id, top }] com top relativo ao topo visível do contêiner.
 * No fim da rolagem a última seção fica ativa, mesmo que seu topo não alcance o limiar.
 */
export const pickActiveSection = ({ sections, scrollTop, scrollHeight, clientHeight, threshold }) => {
  if (!sections?.length) return null;
  if (scrollHeight - clientHeight > 0 && scrollTop + clientHeight >= scrollHeight - 2) {
    return sections[sections.length - 1].id;
  }
  const limit = threshold ?? Math.max(100, clientHeight * 0.3);
  const passed = sections.filter((section) => section.top <= limit);
  return (passed.at(-1) || sections[0]).id;
};

export const isSaveShortcut = (event) => Boolean(
  event && (event.ctrlKey || event.metaKey) && !event.altKey && String(event.key).toLowerCase() === 's',
);

const NON_TEXT_INPUTS = new Set(['button', 'submit', 'reset', 'checkbox', 'radio', 'file', 'image']);

/** Enter em campo de entrada não envia o formulário (salvar é explícito: botão ou Ctrl/Cmd+S). */
export const shouldBlockEnterSubmit = (event) => {
  if (!event || event.key !== 'Enter' || event.isComposing) return false;
  const target = event.target;
  if (!target || String(target.tagName).toUpperCase() !== 'INPUT') return false;
  return !NON_TEXT_INPUTS.has(String(target.type || 'text').toLowerCase());
};

export const isXlsxFile = (file) => Boolean(file) && /\.xlsx$/i.test(String(file.name || ''));

/** Pares [rótulo, valor numérico] que mudaram entre dois resumos; textos são ignorados. */
export const changedSummaryEntries = (previous, next) => {
  if (!previous) return [];
  const before = new Map(previous);
  return next.flatMap(([label, value]) => {
    const old = before.get(label);
    if (typeof value !== 'number' || typeof old !== 'number') return [];
    const delta = value - old;
    return Math.abs(delta) >= 0.005 ? [[label, delta]] : [];
  });
};

export const pluralize = (count, singular, plural) => `${count} ${count === 1 ? singular : plural}`;
