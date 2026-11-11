import React from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { Plus, Trash2 } from 'lucide-react';
import { listItemMotion } from '../orcamentoMotion';
import {
  createDfpItemId,
  getNestedValue,
  nextDfpItemLabel,
  setNestedValue,
  updateDfpCollectionItemAtPath,
  updateDfpField,
} from '../../orcamentoModel';
import { SchemaInput } from './FieldInputs';
import { inputValue, typedInputValue } from './editorShared';

function DiscountField({ disabled, label, onChange, value }) {
  return (
    <label className="orc-field">{label}<input type="number" min="0" max="100" step="0.01" disabled={disabled} value={value || 0} onChange={(event) => onChange(Number(event.target.value))} /></label>
  );
}

function PercentGroup({ disabled, dfp, group, onChange }) {
  const reducedMotion = useReducedMotion();
  const path = `${group.state_key}.items`;
  const items = getNestedValue(dfp, path) || [];
  return (
    <fieldset className="orc-percent-group">
      <legend>{group.title}</legend>
      <AnimatePresence initial={false}>
        {items.map((item) => (
          <motion.div className="orc-percent-field" key={item.id} {...listItemMotion(reducedMotion)}>
            <label className="orc-field"><span>Item</span><input aria-label={`${group.title} · Nome do item ${item.id}`} disabled={disabled} value={item.label} onChange={(event) => onChange(updateDfpCollectionItemAtPath(dfp, path, item.id, 'label', event.target.value))} /></label>
            <label className="orc-field"><span>Alíquota (%)</span><span className="orc-input-suffix">
              <input
                aria-label={`${group.title} · ${item.label}`}
                disabled={disabled}
                max="99.999999"
                min="0"
                onChange={(event) => onChange(updateDfpCollectionItemAtPath(
                  dfp,
                  path,
                  item.id,
                  'aliquot_percent',
                  typedInputValue('number', event.target.value),
                ))}
                step="0.01"
                type="number"
                value={inputValue(item.aliquot_percent)}
              />
              <b>%</b>
            </span></label>
            {/* O nome acessível "Remover" é usado pelos testes e2e. */}
            {!disabled && <button className="orc-btn orc-btn--compact" type="button" onClick={() => onChange(setNestedValue(dfp, path, items.filter((row) => row.id !== item.id)))}><Trash2 aria-hidden="true" />Remover</button>}
          </motion.div>
        ))}
      </AnimatePresence>
      <button type="button" className="orc-btn" disabled={disabled} onClick={() => onChange(setNestedValue(dfp, path, [...items, { id: createDfpItemId(), label: nextDfpItemLabel(items), aliquot_percent: 0 }]))}><Plus aria-hidden="true" />Adicionar item em {group.title}</button>
      {dfp.calculation_version === 2 && group.state_key === 'custos_indiretos' && (
        <DiscountField disabled={disabled} label="Desconto dos custos indiretos (%)" value={dfp.custos_indiretos?.discount_percent} onChange={(value) => onChange(updateDfpField(dfp, 'custos_indiretos', 'discount_percent', value))} />
      )}
    </fieldset>
  );
}

/** Grupos percentuais (impostos, custos indiretos) e o fator BDI. */
export default function PercentGroups({ disabled, dfp, onChange, section }) {
  return (
    <div className="orc-percent-layout">
      {(section.groups || []).map((group) => (
        <PercentGroup disabled={disabled} dfp={dfp} group={group} key={group.state_key} onChange={onChange} />
      ))}
      {section.field && (
        <fieldset className="orc-percent-group orc-percent-group--accent">
          <legend>Bonificação e despesas indiretas</legend>
          {dfp.calculation_version === 2 && (
            <DiscountField disabled={disabled} label="Desconto do BDI (%)" value={dfp.bdi?.discount_percent} onChange={(value) => onChange(updateDfpField(dfp, 'bdi', 'discount_percent', value))} />
          )}
          <SchemaInput
            disabled={disabled}
            field={section.field}
            label={section.field.label}
            onChange={(value) => onChange(updateDfpField(
              dfp,
              section.field.state_key,
              section.field.key,
              value,
            ))}
            options={[]}
            value={getNestedValue(dfp, `${section.field.state_key}.${section.field.key}`)}
          />
        </fieldset>
      )}
    </div>
  );
}
