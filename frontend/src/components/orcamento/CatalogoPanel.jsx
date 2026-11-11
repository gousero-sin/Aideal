import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ChevronDown, Loader2, Plus, Trash2 } from 'lucide-react';
import { createDfpItemId, rotuloResponsavel, validateCatalogoDraft } from '../orcamentoModel';
import { listItemMotion } from './orcamentoMotion';

const formatMoney = (value) => Number(value || 0).toLocaleString('pt-BR', {
  style: 'currency', currency: 'BRL',
});
const formatInstant = (value) => value ? new Date(value).toLocaleString('pt-BR') : 'Vigente';

const GRUPOS = Object.freeze([
  Object.freeze({ group: 'funcoes', title: 'Funções', field: 'salario_real', label: 'Salário real', addLabel: 'Adicionar função' }),
  Object.freeze({ group: 'itens', title: 'Itens', field: 'valor_unitario', label: 'Valor unitário', addLabel: 'Adicionar item ao catálogo' }),
]);

// `_key` é só da tela (chave estável do React); sai antes de comparar ou salvar.
const withKeys = (catalogo) => ({
  ...catalogo,
  ...Object.fromEntries(GRUPOS.map(({ group }) => [group,
    (catalogo?.[group] || []).map((item) => ({ ...item, _key: createDfpItemId() }))])),
});
const withoutKeys = (draft) => ({
  ...draft,
  ...Object.fromEntries(GRUPOS.map(({ group }) => [group,
    (draft?.[group] || []).map(({ _key, ...item }) => item)])),
});
const comparable = (catalogo) => JSON.stringify({
  custo_administrativo_diario: Number(catalogo?.custo_administrativo_diario) || 0,
  ...Object.fromEntries(GRUPOS.map(({ group }) => [group, catalogo?.[group] || []])),
});

export default function CatalogoPanel({ catalogo, currentUserId, historico = [], busy, onSave }) {
  const reducedMotion = useReducedMotion();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(() => withKeys(catalogo));
  const [errors, setErrors] = useState([]);
  const [saving, setSaving] = useState(false);
  const regionId = useId();
  // A carteira recarrega após qualquer mutação; só ressincroniza se o catálogo salvo mudou,
  // para não apagar um rascunho em edição.
  const syncedRef = useRef(comparable(catalogo));
  useEffect(() => {
    const next = comparable(catalogo);
    if (next === syncedRef.current) return;
    syncedRef.current = next;
    setDraft(withKeys(catalogo));
    setErrors([]);
  }, [catalogo]);

  const clean = useMemo(() => withoutKeys(draft), [draft]);
  const dirty = comparable(clean) !== comparable(catalogo);
  const disabled = busy || saving;

  const update = (group, key, field, value) => setDraft((current) => ({ ...current,
    [group]: (current[group] || []).map((item) => item._key === key ? { ...item, [field]: value } : item) }));
  const remove = (group, key) => setDraft((current) => ({ ...current,
    [group]: (current[group] || []).filter((item) => item._key !== key) }));
  const add = (group, field) => setDraft((current) => ({ ...current,
    [group]: [...(current[group] || []), { nome: '', [field]: 0, _key: createDfpItemId() }] }));

  const save = async () => {
    const nextErrors = validateCatalogoDraft(clean);
    setErrors(nextErrors);
    if (nextErrors.length) return;
    setSaving(true);
    try { await onSave(clean); } finally { setSaving(false); }
  };

  return (
    <div className="orc-catalogo" data-open={open || undefined}>
      <button aria-controls={regionId} aria-expanded={open} className="orc-disclosure" onClick={() => setOpen((value) => !value)} type="button">
        <span>Configurações de salários e itens reutilizáveis</span>
        {dirty && <span className="orc-dirty-badge">Alterações não salvas</span>}
        <ChevronDown aria-hidden="true" className="orc-disclosure__chevron" />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            animate={{ height: 'auto', opacity: 1 }}
            className="orc-catalogo__body"
            exit={{ height: 0, opacity: 0 }}
            id={regionId}
            initial={{ height: 0, opacity: 0 }}
            transition={{ duration: reducedMotion ? 0 : 0.22 }}
          >
            <p className="orc-note">Os valores cadastrados são sugestões para novos itens. Cada revisão conserva os valores que foram salvos nela.</p>
            {errors.length > 0 && <div className="orc-validation-error" role="alert">{errors.map((error) => <p key={error}>{error}</p>)}</div>}
            <label className="orc-field orc-catalogo__admin">
              <span>Custo administrativo padrão por dia (R$)</span>
              <input className="orc-num" disabled={disabled} min="0" onChange={(e) => setDraft((current) => ({ ...current, custo_administrativo_diario: Number(e.target.value) }))}
                step="0.01" type="number" value={draft.custo_administrativo_diario || 0} />
            </label>
            {GRUPOS.map(({ group, title, field, label, addLabel }) => (
              <fieldset className="orc-catalogo__group" key={group}>
                <legend>{title} <span className="orc-count">{(draft[group] || []).length}</span></legend>
                {(draft[group] || []).length === 0 && <p className="orc-note">Nenhum cadastro ainda.</p>}
                <AnimatePresence initial={false}>
                  {(draft[group] || []).map((item, index) => (
                    <motion.div className="orc-catalogo__row" key={item._key} layout={!reducedMotion} {...listItemMotion(reducedMotion)}>
                      <label className="orc-field"><span>Nome</span>
                        <input aria-label={`${title} nome ${index + 1}`} disabled={disabled} onChange={(e) => update(group, item._key, 'nome', e.target.value)} value={item.nome} />
                      </label>
                      <label className="orc-field"><span>{label}</span>
                        <input className="orc-num" disabled={disabled} min="0" onChange={(e) => update(group, item._key, field, Number(e.target.value))} step="0.01" type="number" value={item[field]} />
                      </label>
                      <button aria-label={`Remover ${title.toLowerCase()} ${item.nome || index + 1}`} className="orc-btn orc-btn--compact orc-btn--quiet" disabled={disabled} onClick={() => remove(group, item._key)} type="button">
                        <Trash2 aria-hidden="true" /> Remover
                      </button>
                    </motion.div>
                  ))}
                </AnimatePresence>
                <button className="orc-btn orc-btn--quiet" disabled={disabled} onClick={() => add(group, field)} type="button"><Plus aria-hidden="true" /> {addLabel}</button>
              </fieldset>
            ))}
            <div className="orc-button-row orc-catalogo__actions">
              {dirty && <button className="orc-btn" disabled={disabled} onClick={() => { setDraft(withKeys(catalogo)); setErrors([]); }} type="button">Descartar alterações</button>}
              <button className="orc-btn orc-btn--primary" disabled={disabled || !dirty} onClick={save} type="button">
                {saving && <Loader2 className="orc-spin" aria-hidden="true" />} Salvar catálogo
              </button>
            </div>
            {Array.isArray(historico) && historico.length > 0 && <details className="orc-catalog-history">
              <summary>Histórico de vigência ({historico.length})</summary>
              <p>Versões anteriores são somente leitura.</p>
              <div className="orc-catalog-history__list">
                {historico.map((entry) => <details key={entry.versao} className="orc-catalog-history__entry">
                  <summary>
                    <strong>Versão {entry.versao}</strong>
                    <span>{formatInstant(entry.vigente_desde)} → {formatInstant(entry.vigente_ate)}</span>
                  </summary>
                  <p>Responsável: {rotuloResponsavel(entry.responsavel_user_id, currentUserId)}</p>
                  <dl>
                    <div><dt>Custo administrativo / dia</dt><dd>{formatMoney(entry.payload?.custo_administrativo_diario)}</dd></div>
                    <div><dt>Funções</dt><dd>{entry.payload?.funcoes?.length || 0}</dd></div>
                    <div><dt>Itens</dt><dd>{entry.payload?.itens?.length || 0}</dd></div>
                  </dl>
                  {(entry.payload?.funcoes || []).length > 0 && <div className="orc-catalog-history__values">
                    <strong>Funções</strong>
                    {(entry.payload.funcoes || []).map((item, index) => <span key={`${item.nome}-${index}`}>{item.nome}: {formatMoney(item.salario_real)}</span>)}
                  </div>}
                  {(entry.payload?.itens || []).length > 0 && <div className="orc-catalog-history__values">
                    <strong>Itens</strong>
                    {(entry.payload.itens || []).map((item, index) => <span key={`${item.nome}-${index}`}>{item.nome}: {formatMoney(item.valor_unitario)}</span>)}
                  </div>}
                </details>)}
              </div>
            </details>}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
