import React from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { Plus, Trash2 } from 'lucide-react';
import { listItemMotion } from '../orcamentoMotion';
import {
  createDfpItemId,
  getNestedValue,
  setNestedValue,
  updateDfpCollectionItemAtPath,
} from '../../orcamentoModel';

const PATH = 'mao_de_obra_direta.adjustments';
const NUMBER_FIELDS = [
  { key: 'quantity', label: 'Pessoas', step: 1 },
  { key: 'percent', label: 'Percentual (%)', step: 0.01, max: '99.999999' },
];

/** Adicionais da mão de obra direta (periculosidade, insalubridade etc.) por função. */
export default function AdjustmentsEditor({ disabled, dfp, onChange }) {
  const reducedMotion = useReducedMotion();
  const adjustments = getNestedValue(dfp, PATH) || [];
  const laborRows = dfp.mao_de_obra_direta?.items || [];
  const update = (item, key, value) => onChange(updateDfpCollectionItemAtPath(dfp, PATH, item.id, key, value));
  const add = () => onChange(setNestedValue(dfp, PATH, [...adjustments, {
    id: createDfpItemId(), label: 'Novo adicional', quantity: 0, percent: 0, labor_item_id: '', base: 'salary',
  }]));
  const remove = (item) => onChange(setNestedValue(dfp, PATH, adjustments.filter((adjustment) => adjustment.id !== item.id)));

  return (
    <div className="orc-section-stack">
      <AnimatePresence initial={false}>
        {adjustments.map((item) => (
          <motion.fieldset className="orc-percent-group" key={item.id} {...listItemMotion(reducedMotion)}>
            <legend>{item.label}</legend>
            <div className="orc-field-grid">
              <label className="orc-field">Nome<input disabled={disabled} value={item.label} onChange={(event) => update(item, 'label', event.target.value)} /></label>
              <label className="orc-field">Função<select disabled={disabled} value={item.labor_item_id || ''} onChange={(event) => update(item, 'labor_item_id', event.target.value)}><option value="">Selecione a função</option>{laborRows.map((row) => <option value={row.id} key={row.id}>{row.label}</option>)}</select></label>
              {NUMBER_FIELDS.map((field) => (
                <label className="orc-field" key={field.key}>{field.label}<input disabled={disabled} type="number" min="0" max={field.max} step={field.step} value={item[field.key] || 0} onChange={(event) => update(item, field.key, Number(event.target.value))} /></label>
              ))}
              <label className="orc-field">Base de incidência<select disabled={disabled} value={item.base || 'salary'} onChange={(event) => update(item, 'base', event.target.value)}><option value="salary">Salário</option><option value="salary_and_overtime">Salário e horas extras</option></select></label>
            </div>
            {!disabled && <button className="orc-btn orc-btn--compact" type="button" onClick={() => remove(item)}><Trash2 aria-hidden="true" />Remover adicional</button>}
          </motion.fieldset>
        ))}
      </AnimatePresence>
      <button className="orc-btn" type="button" disabled={disabled} onClick={add}><Plus aria-hidden="true" />Adicionar adicional</button>
    </div>
  );
}
