import React, { useEffect, useState } from 'react';
import { validateCatalogoDraft } from '../orcamentoModel';

const formatMoney = (value) => Number(value || 0).toLocaleString('pt-BR', {
  style: 'currency', currency: 'BRL',
});
const formatInstant = (value) => value ? new Date(value).toLocaleString('pt-BR') : 'Vigente';

export default function CatalogoPanel({ catalogo, historico = [], busy, onSave }) {
  const [draft, setDraft] = useState(catalogo);
  const [errors, setErrors] = useState([]);
  useEffect(() => { setDraft(catalogo); setErrors([]); }, [catalogo]);
  const update = (group, index, field, value) => setDraft((current) => ({ ...current,
    [group]: (current[group] || []).map((item, i) => i === index ? { ...item, [field]: value } : item) }));
  const save = () => {
    const nextErrors = validateCatalogoDraft(draft);
    setErrors(nextErrors);
    if (nextErrors.length === 0) onSave(draft);
  };
  return <details className="orc-catalogo"><summary>Configurações de salários e itens reutilizáveis</summary>
    <p>Os valores cadastrados são sugestões para novos itens. Cada revisão conserva os valores que foram salvos nela.</p>
    {errors.length > 0 && <div className="orc-validation-error" role="alert">{errors.map((error) => <p key={error}>{error}</p>)}</div>}
    <label className="orc-field">Custo administrativo padrão por dia (R$)<input type="number" min="0" step="0.01" disabled={busy}
      value={draft.custo_administrativo_diario || 0} onChange={(e) => setDraft({ ...draft, custo_administrativo_diario: Number(e.target.value) })} /></label>
    {[['funcoes', 'Funções', 'salario_real', 'Salário real'], ['itens', 'Itens', 'valor_unitario', 'Valor unitário']].map(([group, title, field, label]) =>
      <fieldset key={group}><legend>{title}</legend>
        {(draft[group] || []).map((item, index) => <div className="orc-field-grid" key={index}>
          <label className="orc-field">Nome<input aria-label={`${title} nome ${index + 1}`} disabled={busy} value={item.nome} onChange={(e) => update(group, index, 'nome', e.target.value)} /></label>
          <label className="orc-field">{label}<input type="number" min="0" step="0.01" disabled={busy} value={item[field]} onChange={(e) => update(group, index, field, Number(e.target.value))} /></label>
          <button className="orc-btn orc-btn--compact" type="button" disabled={busy} onClick={() => setDraft((current) => ({ ...current, [group]: (current[group] || []).filter((_, i) => i !== index) }))}>Remover</button>
        </div>)}
        <button className="orc-btn" type="button" disabled={busy} onClick={() => setDraft({ ...draft, [group]: [...(draft[group] || []), { nome: '', [field]: 0 }] })}>Adicionar {group === 'funcoes' ? 'função' : 'item ao catálogo'}</button>
      </fieldset>)}
    <button className="orc-btn orc-btn--primary" type="button" disabled={busy} onClick={save}>Salvar catálogo</button>
    {Array.isArray(historico) && historico.length > 0 && <details className="orc-catalog-history">
      <summary>Histórico de vigência ({historico.length})</summary>
      <p>Versões anteriores são somente leitura.</p>
      <div className="orc-catalog-history__list">
        {historico.map((entry) => <details key={entry.versao} className="orc-catalog-history__entry">
          <summary>
            <strong>Versão {entry.versao}</strong>
            <span>{formatInstant(entry.vigente_desde)} → {formatInstant(entry.vigente_ate)}</span>
          </summary>
          <p>Responsável: {entry.responsavel_user_id}</p>
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
  </details>;
}
