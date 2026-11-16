import React from 'react';
import { Eraser, FilePlus2, Loader2, Plus } from 'lucide-react';
import OrcamentoDialog from './OrcamentoDialog';
import StartDateField from './StartDateField';
import { LocationHeaderField } from './editor/FieldInputs';
import { CAMPOS_CABECALHO } from '../orcamentoModel';

function CreateFields({ disabled, errors, form, onChange, onDfpChange }) {
  return (
    <div className="orc-field-grid orc-create-grid">
      {CAMPOS_CABECALHO.map(({ field, label, long, options, type }) => field === 'regiao' ? (
        <LocationHeaderField disabled={disabled} error={errors[field]} form={form} idPrefix="orc-create-location" key={field} onDfpChange={onDfpChange} />
      ) : field === 'dataInicio' ?
        <StartDateField key={field} value={form[field]} disabled={disabled} error={errors[field]} onChange={(value) => onChange(field, value)} /> : (
        <label className={`orc-field ${long ? 'orc-field--wide' : ''}`} key={field}>
          <span>{label}</span>
          {long ? (
            <textarea aria-invalid={Boolean(errors[field])} disabled={disabled} onChange={(event) => onChange(field, event.target.value)} rows="2" value={form[field] ?? ''} />
          ) : options ? (
            <select aria-invalid={Boolean(errors[field])} disabled={disabled} onChange={(event) => onChange(field, event.target.value)} value={form[field] ?? ''}>
              <option value="">Selecione</option>
              {options.map((option) => <option value={option} key={option}>{option}</option>)}
            </select>
          ) : (
            <input aria-invalid={Boolean(errors[field])} disabled={disabled} min={type === 'number' ? '0' : undefined} onChange={(event) => onChange(field, event.target.value)} type={type || 'text'} value={form[field] ?? ''} />
          )}
          {errors[field] && <small role="alert">{errors[field]}</small>}
        </label>
      ))}
    </div>
  );
}

/**
 * Criação de orçamento em diálogo. O rascunho do formulário pertence ao painel: fechar o
 * diálogo não perde o que já foi digitado.
 */
export default function CreateBudgetDialog({
  budgets, busy, error, errors, form, onChange, onClose, onDfpChange, onReset, onReuse, onSubmit, reuseId, saving,
}) {
  return (
    <OrcamentoDialog
      busy={saving}
      className="orc-create-window"
      description="Só a contratante é obrigatória agora. O restante pode ser completado no editor."
      icon={FilePlus2}
      onClose={onClose}
      title="Novo orçamento"
    >
      <form noValidate onSubmit={onSubmit}>
        {budgets.length > 0 && (
          <div className="orc-reuse-row">
            <label className="orc-field orc-reuse-field">
              <span>Preencher a partir de orçamento existente</span>
              <select disabled={busy} onChange={(event) => onReuse(event.target.value)} value={reuseId}>
                <option value="">Selecione para reaproveitar dados</option>
                {budgets.map((budget) => <option key={budget.id} value={budget.id}>{budget.codigo} — {budget.contratante}</option>)}
              </select>
            </label>
            <button className="orc-btn orc-btn--quiet" disabled={busy} onClick={onReset} type="button"><Eraser aria-hidden="true" /> Limpar formulário</button>
          </div>
        )}
        <CreateFields disabled={busy} errors={errors} form={form} onChange={onChange} onDfpChange={onDfpChange} />
        {error && <p className="orc-validation-error" role="alert">{error}</p>}
        <div className="orc-work-dialog__footer">
          <button className="orc-btn" disabled={saving} onClick={onClose} type="button">Cancelar</button>
          <button className="orc-btn orc-btn--primary" disabled={busy} type="submit">
            {saving ? <Loader2 className="orc-spin" aria-hidden="true" /> : <Plus aria-hidden="true" />} Criar orçamento
          </button>
        </div>
      </form>
    </OrcamentoDialog>
  );
}
