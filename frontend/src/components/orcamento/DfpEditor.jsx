import React, { createContext, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import StartDateField from './StartDateField';
import { useHhSections } from './HhEditor';
import { collectHhWarnings, mesesDoPrazo } from './hhModel';
import brazilLocations from '../../data/brazilLocations.json';
import {
  BadgeDollarSign,
  BookOpenCheck,
  Calculator,
  FileText,
  LockKeyhole,
  Maximize2,
  Minimize2,
  Minus,
  Save,
  X,
} from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import useOrcamentoDialog from './useOrcamentoDialog';
import { windowMotion } from './orcamentoMotion';
import { GoFlowWindow } from '../goflow-window';
import {
  CAMPOS_REVISAO,
  collectOrcamentoWarnings,
  computeDfpSummary,
  createDfpItemId,
  inheritedLaborDays,
  INHERITED_LABOR_DAYS,
  computeLaborRow,
  computeSectionTotal,
  computeTableRowSubtotal,
  removeDfpCollectionItem,
  nextDfpItemLabel,
  setNestedValue,
  getDfpSectionStatePath,
  getNestedValue,
  getSchemaSections,
  updateDfpCollectionItemAtPath,
  updateDfpField,
} from '../orcamentoModel';

const formatMoney = (value) => Number(value || 0).toLocaleString('pt-BR', {
  style: 'currency',
  currency: 'BRL',
});
const formatPercent = (value) => `${Number(value || 0).toLocaleString('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})}%`;
// Valores calculados (hora, horas trabalhadas) chegam com dízimas; o campo é só leitura.
const COMPUTED_LABOR_COLUMNS = new Set(['worked_hours', 'hourly_rate']);
const roundComputed = (value) => (Number.isFinite(Number(value)) ? Math.round(Number(value) * 100) / 100 : value);

const inputValue = (value) => value ?? '';
const CatalogContext = createContext({ funcoes: [], itens: [], custo_administrativo_diario: 0 });
const NATURAL_LABOR_COLUMNS = new Set(['quantity', 'worked_days', 'saturday_days', 'sunday_days', 'mobilization_days']);
const INHERITED_LABOR_COLUMNS = new Set(Object.keys(INHERITED_LABOR_DAYS));
const HIDDEN_V2_LABOR_COLUMNS = new Set(['hours_per_employee', 'salary_base_hours', 'manual_total']);
const BRAZIL_STATES = brazilLocations.states || [];
const BRAZIL_STATES_BY_CODE = new Map(BRAZIL_STATES.map((state) => [state.code, state]));
const typedInputValue = (type, value) => (
  type === 'number' && value !== '' ? Number(value) : value
);

function HeaderFields({ disabled, errors, form, onChange, onDfpChange }) {
  return (
    <div className="orc-field-grid">
      {CAMPOS_REVISAO.map(({ field, label, long, options, type }) => field === 'regiao' ? (
        <LocationHeaderField disabled={disabled} error={errors[field]} form={form} key={field} onDfpChange={onDfpChange} />
      ) : field === 'dataInicio' ?
        <StartDateField key={field} value={form[field]} disabled={disabled} error={errors[field]} onChange={(value) => onChange(field, value)} /> : (
        <label className={`orc-field ${long ? 'orc-field--wide' : ''}`} key={field}>
          <span>{label}</span>
          {long ? (
            <textarea
              aria-invalid={Boolean(errors[field])}
              disabled={disabled}
              onChange={(event) => onChange(field, event.target.value)}
              rows={3}
              value={inputValue(form[field])}
            />
          ) : options ? (
            <select
              aria-invalid={Boolean(errors[field])}
              disabled={disabled}
              onChange={(event) => onChange(field, event.target.value)}
              value={inputValue(form[field])}
            >
              <option value="">Selecione</option>
              {options.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
          ) : (
            <input
              aria-invalid={Boolean(errors[field])}
              disabled={disabled}
              min={type === 'number' ? '0' : undefined}
              onChange={(event) => onChange(field, event.target.value)}
              step={field === 'prazoExecucaoDias' ? '1' : undefined}
              type={type || 'text'}
              value={inputValue(form[field])}
            />
          )}
          {errors[field] && <small role="alert">{errors[field]}</small>}
        </label>
      ))}
    </div>
  );
}

function SchemaInput({ disabled, field, label, onChange, options, value }) {
  const id = `${field.key}-${String(label).replace(/\W+/g, '-').toLowerCase()}`;
  const strictPercent = ['social_charges_percent', 'factor_percent'].includes(field.key);
  const boundedPercent = ['considered_percent', 'discount_percent'].includes(field.key);
  if (field.type === 'boolean') {
    return (
      <label className="orc-check" htmlFor={id}>
        <input
          checked={Boolean(value)}
          disabled={disabled}
          id={id}
          onChange={(event) => onChange(event.target.checked)}
          type="checkbox"
        />
        <span>{label}</span>
      </label>
    );
  }

  return (
    <label className={`orc-field ${field.type === 'textarea' ? 'orc-field--wide' : ''}`} htmlFor={id}>
      <span>{label}</span>
      {field.type === 'textarea' ? (
        <textarea
          disabled={disabled}
          id={id}
          onChange={(event) => onChange(typedInputValue(field.type, event.target.value))}
          rows={3}
          value={inputValue(value)}
        />
      ) : field.type === 'select' ? (
        <select
          disabled={disabled}
          id={id}
          onChange={(event) => onChange(event.target.value)}
          value={inputValue(value)}
        >
          <option value="">Selecione</option>
          {options.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      ) : (
        <input
          disabled={disabled}
          id={id}
          max={strictPercent ? '99.999999' : boundedPercent ? '100' : undefined}
          min={field.type === 'number' ? '0' : undefined}
          onChange={(event) => onChange(typedInputValue(field.type, event.target.value))}
          step={field.step}
          type={field.type || 'text'}
          value={inputValue(value)}
        />
      )}
    </label>
  );
}

export function LocationSelectors({ disabled, dfp, idPrefix = 'orc-location', includeCountry = true, onChange, statePath }) {
  const metadata = getNestedValue(dfp, statePath) || {};
  const country = metadata.pais || brazilLocations.country;
  const selectedState = BRAZIL_STATES_BY_CODE.get(String(metadata.uf || '').toUpperCase());
  const selectedCity = metadata.municipio || '';
  const cities = selectedState?.cities || [];

  const updateLocation = (changes) => {
    let next = dfp;
    Object.entries(changes).forEach(([key, value]) => {
      next = updateDfpField(next, statePath, key, value);
    });
    onChange(next);
  };

  return (
    <>
      {includeCountry && <label className="orc-field" htmlFor={`${idPrefix}-country`}>
        <span>País</span>
        <select
          disabled={disabled}
          aria-label="País"
          id={`${idPrefix}-country`}
          onChange={(event) => updateLocation({
            pais: event.target.value,
            uf: '',
            municipio: '',
            macrorregiao: '',
          })}
          value={country}
        >
          <option value="Brasil">Brasil</option>
          {country !== 'Brasil' && <option value={country}>{country} (legado)</option>}
        </select>
      </label>}

      <label className="orc-field" htmlFor={`${idPrefix}-state`}>
        <span>Estado</span>
        <select
          disabled={disabled || country !== 'Brasil'}
          aria-label="Estado"
          id={`${idPrefix}-state`}
          onChange={(event) => {
            const state = BRAZIL_STATES_BY_CODE.get(event.target.value);
            updateLocation({
              pais: 'Brasil',
              uf: event.target.value,
              municipio: '',
              macrorregiao: state?.region || '',
            });
          }}
          value={metadata.uf || ''}
        >
          <option value="">Selecione o estado</option>
          {BRAZIL_STATES.map((state) => (
            <option key={state.code} value={state.code}>{state.name} ({state.code})</option>
          ))}
          {metadata.uf && !selectedState && <option value={metadata.uf}>{metadata.uf} (legado)</option>}
        </select>
      </label>

      <label className="orc-field" htmlFor={`${idPrefix}-city`}>
        <span>Cidade</span>
        <select
          disabled={disabled || !selectedState}
          aria-label="Cidade"
          id={`${idPrefix}-city`}
          onChange={(event) => updateLocation({ pais: 'Brasil', municipio: event.target.value })}
          value={selectedCity}
        >
          <option value="">{selectedState ? 'Selecione a cidade' : 'Selecione o estado primeiro'}</option>
          {cities.map((city) => <option key={city} value={city}>{city}</option>)}
          {selectedCity && !cities.includes(selectedCity) && <option value={selectedCity}>{selectedCity} (legado)</option>}
        </select>
      </label>
    </>
  );
}

export function LocationHeaderField({ disabled, error, form, idPrefix = 'orc-header-location', onDfpChange }) {
  return (
    <fieldset className="orc-location-header">
      <legend>Região da Obra</legend>
      <div className="orc-location-header__grid">
        <LocationSelectors
          disabled={disabled}
          dfp={form.dfp}
          idPrefix={idPrefix}
          onChange={onDfpChange}
          statePath="metadata"
        />
      </div>
      <output aria-label="Região selecionada" className="orc-location-header__value">
        {form.regiao || 'Selecione o estado e a cidade'}
      </output>
      {error && <small role="alert">{error}</small>}
    </fieldset>
  );
}

function FieldsSection({ disabled, dfp, onChange, schema, section }) {
  const catalog = useContext(CatalogContext);
  const statePath = getDfpSectionStatePath(section);
  const selectOptions = schema?.options?.forma_tributacao || [];
  const fields = (section.fields || []).filter((field) => !(
    statePath === 'metadata' && field.key === 'codigo_dfp'
  ));
  return (
    <div className="orc-field-grid">
      {section.id === 'custos_administrativos' && <div><p>Total: {formatMoney(computeSectionTotal(dfp, 'custos_administrativos'))}</p>
        <button className="orc-btn" type="button" disabled={disabled} onClick={() => onChange(updateDfpField(dfp, statePath, 'daily_cost', catalog.custo_administrativo_diario || 0))}>Usar custo diário cadastrado</button></div>}
      {fields.map((field) => {
        if (statePath === 'metadata' && ['pais', 'uf', 'municipio', 'macrorregiao'].includes(field.key)) return null;
        return (
          <SchemaInput
            disabled={disabled}
            field={field}
            key={field.key}
            label={field.label}
            onChange={(value) => onChange(updateDfpField(dfp, statePath, field.key, value))}
            options={field.type === 'select' ? selectOptions : []}
            value={getNestedValue(dfp, `${statePath}.${field.key}`)}
          />
        );
      })}
    </div>
  );
}

function DataTable({ collectionPath, columns, disabled, dfp, onChange, sectionTitle }) {
  const catalog = useContext(CatalogContext);
  const suggestions = collectionPath.startsWith('mao_de_obra') ? catalog.funcoes || [] : catalog.itens || [];
  const listId = `catalog-${collectionPath.replaceAll('.', '-')}`;
  const items = getNestedValue(dfp, collectionPath);
  const bottom = useRef(null);
  const top = useRef(null);
  const [width, setWidth] = useState(2000);
  useLayoutEffect(() => {
    const table = bottom.current?.querySelector('table');
    if (!table) return undefined;
    const observer = new ResizeObserver(() => setWidth(table.scrollWidth));
    observer.observe(table);
    return () => observer.disconnect();
  }, [columns]);
  const sectionPath = collectionPath.replace(/\.items$/, '');
  const isUpdatedLabor = dfp.calculation_version === 2 && collectionPath === 'mao_de_obra_direta.items';
  const visibleColumns = isUpdatedLabor
    ? columns.filter((column) => !HIDDEN_V2_LABOR_COLUMNS.has(column.key))
    : columns;
  const canRemoveRows = dfp.calculation_version === 2 && !disabled;
  const total = computeSectionTotal(dfp, sectionPath);
  const directTotal = computeDfpSummary(dfp).custosDiretosTotal;
  const peopleDays = (dfp.mao_de_obra_direta?.items || []).reduce((sum, row) => sum + computeLaborRow(row, dfp).allDays * Number(row.quantity || 0), 0);
  const changeName = (item, name) => {
    const suggestion = suggestions.find((entry) => entry.nome.toLocaleLowerCase() === name.toLocaleLowerCase());
    const changed = updateDfpCollectionItemAtPath(dfp, collectionPath, item.id, 'label', name);
    onChange(suggestion ? updateDfpCollectionItemAtPath(changed, collectionPath, item.id,
      collectionPath.startsWith('mao_de_obra') ? 'salary_real' : 'unit_cost', suggestion.salario_real ?? suggestion.valor_unitario) : changed);
  };
  return (
    <div className="orc-table-shell">
    <div className="orc-table-scroll-top" ref={top} onScroll={() => { if (bottom.current) bottom.current.scrollLeft = top.current.scrollLeft; }} aria-label={`Rolagem superior de ${sectionTitle}`} tabIndex={0}><div style={{ width, height: 1 }} /></div>
    <div ref={bottom} onScroll={() => { if (top.current) top.current.scrollLeft = bottom.current.scrollLeft; }} className="orc-table-scroll" data-scroll-key={collectionPath} tabIndex="0" role="region" aria-label={`${sectionTitle}, tabela rolável`}>
      <datalist id={listId}>{suggestions.map((entry) => <option key={entry.nome} value={entry.nome} />)}</datalist>
      <table className="orc-dfp-table">
        <thead>
          <tr>
            <th scope="col">Item</th>
            {visibleColumns.map((column) => <th key={column.key} scope="col">{column.label}</th>)}
            <th scope="col">{collectionPath.startsWith('mao_de_obra') ? 'Subtotal antes de adicionais e encargos' : 'Subtotal'}</th>
            {canRemoveRows && <th scope="col">Ações</th>}
          </tr>
        </thead>
        <tbody>
          {(Array.isArray(items) ? items : []).map((item) => (
            <tr key={item.id}>
              <th scope="row"><input list={listId} aria-label={`${sectionTitle} · Nome do item ${item.id}`} disabled={disabled} title={item.label} value={item.label} onChange={(event) => changeName(item, event.target.value)} /></th>
              {visibleColumns.map((column) => (
                <td key={column.key}>
                  <input
                    aria-label={`${sectionTitle} · ${item.label} · ${column.label}`}
                    className={column.type === 'number' ? 'orc-num' : undefined}
                    disabled={disabled}
                    readOnly={column.readonly || column.read_only || (isUpdatedLabor && ['worked_hours', 'hourly_rate'].includes(column.key))}
                    min={column.type === 'number' ? '0' : undefined}
                    onChange={(event) => onChange(updateDfpCollectionItemAtPath(
                      dfp,
                      collectionPath,
                      item.id,
                      column.key,
                      typedInputValue(column.type, event.target.value),
                    ))}
                    step={column.key === 'hourly_rate' ? 'any' : isUpdatedLabor && NATURAL_LABOR_COLUMNS.has(column.key) ? '1' : column.step}
                    type={column.type || 'text'}
                    placeholder={isUpdatedLabor && INHERITED_LABOR_COLUMNS.has(column.key)
                      ? String(inheritedLaborDays(dfp, column.key)) : undefined}
                    title={isUpdatedLabor && INHERITED_LABOR_COLUMNS.has(column.key)
                      ? `Em branco usa ${inheritedLaborDays(dfp, column.key)}, o valor de Identificação e Escopo. Digite 0 para não considerar.`
                      : undefined}
                    value={inputValue(dfp.calculation_version === 2 && collectionPath === 'alimentacao.items' && column.key === 'quantity' ? peopleDays : isUpdatedLabor ? (COMPUTED_LABOR_COLUMNS.has(column.key) ? roundComputed(computeLaborRow(item, dfp)[column.key]) : computeLaborRow(item, dfp)[column.key]) : item[column.key])}
                  />
                </td>
              ))}
              <td className="orc-num-cell">{formatMoney(computeTableRowSubtotal(dfp, collectionPath, item))}</td>
              {canRemoveRows && <td><button className="orc-btn orc-btn--compact" type="button" aria-label={`Remover ${sectionTitle} · ${item.label}`} onClick={() => onChange(removeDfpCollectionItem(dfp, collectionPath, item.id))}>Remover</button></td>}
            </tr>
          ))}
        </tbody>
        {/* O valor fica na coluna fixa: na última coluna ele some atrás da rolagem horizontal. */}
        <tfoot><tr><th scope="row" className="orc-table-total"><span>Total</span><strong>{formatMoney(total)}</strong><small>{formatPercent(directTotal ? (100 * total) / directTotal : 0)} dos custos diretos</small></th><td colSpan={visibleColumns.length} /><td className="orc-num-cell orc-num-cell--strong">{formatMoney(total)}</td>{canRemoveRows && <td />}</tr></tfoot>
      </table>
    </div>
    <div className="orc-table-actions">
      <button type="button" className="orc-btn" disabled={disabled} onClick={() => onChange(setNestedValue(dfp, collectionPath, [...(items || []), { ...Object.fromEntries(visibleColumns.map((column) => [column.key, ['worked_days', 'saturday_days', 'sunday_days'].includes(column.key) ? null : column.type === 'number' ? 0 : ''])), id: createDfpItemId(), label: nextDfpItemLabel(items) }]))}>Adicionar item</button>
      {dfp.calculation_version === 2 && <label className="orc-field">Desconto do subtópico (%)<input type="number" min="0" max="100" step="0.01" disabled={disabled} value={getNestedValue(dfp, `${sectionPath}.discount_percent`) || 0} onChange={(event) => onChange(updateDfpField(dfp, sectionPath, 'discount_percent', Number(event.target.value)))} /></label>}
    </div>
    </div>
  );
}

function LaborSection({ disabled, dfp, onChange, section }) {
  const statePath = getDfpSectionStatePath(section);
  const adjustments = getNestedValue(dfp, `${statePath}.adjustments`) || [];
  const footer = section.footer_field;
  return (
    <div className="orc-section-stack">
      <DataTable
        collectionPath={`${statePath}.items`}
        columns={section.columns || []}
        disabled={disabled}
        dfp={dfp}
        onChange={onChange}
        sectionTitle={section.title}
      />
      <div className="orc-adjustments" aria-label={`Ajustes de ${section.title}`}>
        {dfp.calculation_version !== 2 && adjustments.map((adjustment) => (
          <label className="orc-field" key={adjustment.id}>
            <span>{adjustment.label} (%)</span>
            <input
              aria-label={`${section.title} · ${adjustment.label}`}
              disabled={disabled}
              min="0"
              onChange={(event) => onChange(updateDfpCollectionItemAtPath(
                dfp,
                `${statePath}.adjustments`,
                adjustment.id,
                'percent',
                typedInputValue('number', event.target.value),
              ))}
              step="0.01"
              type="number"
              value={inputValue(adjustment.percent)}
            />
          </label>
        ))}
        {footer && (
          <SchemaInput
            disabled={disabled}
            field={footer}
            label={footer.label}
            onChange={(value) => onChange(updateDfpField(dfp, statePath, footer.key, value))}
            options={[]}
            value={getNestedValue(dfp, `${statePath}.${footer.key}`)}
          />
        )}
      </div>
    </div>
  );
}

function CostSection({ disabled, dfp, onChange, section }) {
  const path = getDfpSectionStatePath(section);
  const collectionPath = Array.isArray(getNestedValue(dfp, path)) ? path : `${path}.items`;
  return (
    <DataTable
      collectionPath={collectionPath}
      columns={section.columns || []}
      disabled={disabled}
      dfp={dfp}
      onChange={onChange}
      sectionTitle={section.title}
    />
  );
}

function PercentSection({ disabled, dfp, onChange, section }) {
  return (
    <div className="orc-percent-layout">
      {(section.groups || []).map((group) => (
        <fieldset className="orc-percent-group" key={group.state_key}>
          <legend>{group.title}</legend>
          {(getNestedValue(dfp, `${group.state_key}.items`) || []).map((item) => (
            <div className="orc-percent-field" key={item.id}>
              <label className="orc-field"><span>Item</span><input aria-label={`${group.title} · Nome do item ${item.id}`} disabled={disabled} value={item.label} onChange={(event) => onChange(updateDfpCollectionItemAtPath(dfp, `${group.state_key}.items`, item.id, 'label', event.target.value))} /></label>
              <label className="orc-field"><span>Alíquota (%)</span><span className="orc-input-suffix">
                <input
                  aria-label={`${group.title} · ${item.label}`}
                  disabled={disabled}
                  max="99.999999"
                  min="0"
                  onChange={(event) => onChange(updateDfpCollectionItemAtPath(
                    dfp,
                    `${group.state_key}.items`,
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
              {!disabled && <button className="orc-btn orc-btn--compact" type="button" onClick={() => onChange(setNestedValue(dfp, `${group.state_key}.items`, (getNestedValue(dfp, `${group.state_key}.items`) || []).filter((row) => row.id !== item.id)))}>Remover</button>}
            </div>
          ))}
          <button type="button" className="orc-btn" disabled={disabled} onClick={() => onChange(setNestedValue(dfp, `${group.state_key}.items`, [...(getNestedValue(dfp, `${group.state_key}.items`) || []), { id: createDfpItemId(), label: nextDfpItemLabel(getNestedValue(dfp, `${group.state_key}.items`)), aliquot_percent: 0 }]))}>Adicionar item em {group.title}</button>
          {dfp.calculation_version === 2 && group.state_key === 'custos_indiretos' && <label className="orc-field">Desconto dos custos indiretos (%)<input type="number" min="0" max="100" step="0.01" disabled={disabled} value={dfp.custos_indiretos?.discount_percent || 0} onChange={(event) => onChange(updateDfpField(dfp, 'custos_indiretos', 'discount_percent', Number(event.target.value)))} /></label>}
        </fieldset>
      ))}
      {section.field && (
        <fieldset className="orc-percent-group orc-percent-group--accent">
          <legend>Bonificação e despesas indiretas</legend>
          {dfp.calculation_version === 2 && <label className="orc-field">Desconto do BDI (%)<input type="number" min="0" max="100" step="0.01" disabled={disabled} value={dfp.bdi?.discount_percent || 0} onChange={(event) => onChange(updateDfpField(dfp, 'bdi', 'discount_percent', Number(event.target.value)))} /></label>}
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

function SchemaSection({ disabled, dfp, onChange, schema, section }) {
  if (section.kind === 'labor-adjustments') {
    const path = 'mao_de_obra_direta.adjustments';
    const adjustments = getNestedValue(dfp, path) || [];
    return <div className="orc-section-stack">{adjustments.map((item) => <fieldset className="orc-percent-group" key={item.id}>
      <legend>{item.label}</legend><div className="orc-field-grid">
        <label className="orc-field">Nome<input disabled={disabled} value={item.label} onChange={(e) => onChange(updateDfpCollectionItemAtPath(dfp, path, item.id, 'label', e.target.value))} /></label>
        <label className="orc-field">Função<select disabled={disabled} value={item.labor_item_id || ''} onChange={(e) => onChange(updateDfpCollectionItemAtPath(dfp, path, item.id, 'labor_item_id', e.target.value))}><option value="">Selecione a função</option>{(dfp.mao_de_obra_direta?.items || []).map((row) => <option value={row.id} key={row.id}>{row.label}</option>)}</select></label>
        {['quantity', 'percent'].map((key) => <label className="orc-field" key={key}>{key === 'quantity' ? 'Pessoas' : 'Percentual (%)'}<input disabled={disabled} type="number" min="0" max={key === 'percent' ? '99.999999' : undefined} step={key === 'quantity' ? 1 : 0.01} value={item[key] || 0} onChange={(e) => onChange(updateDfpCollectionItemAtPath(dfp, path, item.id, key, Number(e.target.value)))} /></label>)}
        <label className="orc-field">Base de incidência<select disabled={disabled} value={item.base || 'salary'} onChange={(e) => onChange(updateDfpCollectionItemAtPath(dfp, path, item.id, 'base', e.target.value))}><option value="salary">Salário</option><option value="salary_and_overtime">Salário e horas extras</option></select></label>
      </div>{!disabled && <button className="orc-btn orc-btn--compact" type="button" onClick={() => onChange(setNestedValue(dfp, path, adjustments.filter((adjustment) => adjustment.id !== item.id)))}>Remover adicional</button>}</fieldset>)}<button className="orc-btn" type="button" disabled={disabled} onClick={() => onChange(setNestedValue(dfp, path, [...adjustments, { id: createDfpItemId(), label: 'Novo adicional', quantity: 0, percent: 0, labor_item_id: '', base: 'salary' }]))}>Adicionar adicional</button></div>;
  }
  if (section.kind === 'fields') {
    return <FieldsSection disabled={disabled} dfp={dfp} onChange={onChange} schema={schema} section={section} />;
  }
  if (section.kind === 'labor-table') {
    return <LaborSection disabled={disabled} dfp={dfp} onChange={onChange} section={section} />;
  }
  if (section.kind === 'cost-table') {
    return <CostSection disabled={disabled} dfp={dfp} onChange={onChange} section={section} />;
  }
  if (section.kind === 'percent-groups') {
    return <PercentSection disabled={disabled} dfp={dfp} onChange={onChange} section={section} />;
  }
  return <p className="orc-note">Seção indisponível nesta versão do editor.</p>;
}

function SummaryWindow({ dfp, hhSummary, prazoDias }) {
  const reducedMotion = useReducedMotion();
  const dfpSummary = useMemo(() => computeDfpSummary(dfp), [dfp]);
  const summary = hhSummary || dfpSummary;
  const warnings = useMemo(
    () => (hhSummary ? collectHhWarnings(dfp?.hh) : collectOrcamentoWarnings(dfp, { prazoDias })),
    [dfp, hhSummary, prazoDias],
  );
  const items = hhSummary ? [
    ['Colaboradores', hhSummary.colaboradores.toLocaleString('pt-BR')],
    ['Encargos sociais', `${hhSummary.encargos.totalPercent.toLocaleString('pt-BR', { maximumFractionDigits: 4 })}%`],
    ['Total mensal', hhSummary.totalMensal],
    ['Prazo do contrato', `${hhSummary.meses.toLocaleString('pt-BR')} mês(es)`],
    ['Custos diretos no prazo', hhSummary.custosDiretosTotal],
    ['Despesas indiretas no prazo', hhSummary.custosIndiretosTotal],
    ['Lucro no prazo', hhSummary.lucroTotal],
    ['Tributos', `${hhSummary.aliquotaImpostosTotal.toLocaleString('pt-BR')}%`],
  ] : [
    ['Custos diretos', summary.custosDiretosTotal],
    ['Custos indiretos', summary.custosIndiretosTotal],
    ['Lucro / BDI', summary.lucroTotal],
    ['Custos totais', summary.custosTotais],
    ['Impostos', `${summary.aliquotaImpostosTotal.toLocaleString('pt-BR')}%`],
    ['Preço por área', formatMoney(summary.precoPorArea)],
    ['Valor dia / colaborador', formatMoney(summary.valorDiaColaborador)],
  ];
  return (
    <GoFlowWindow
      className="orc-summary-window"
      eyebrow="Cálculo em tempo real"
      icon={BadgeDollarSign}
      id="orc-section-summary"
      title="Impostos e resumo"
    >
      {warnings.length > 0 && (
        <ul className="orc-summary-warnings" role="status" aria-label="Avisos do cálculo">
          {warnings.map((warning) => <li key={warning}>{warning}</li>)}
        </ul>
      )}
      <dl className="orc-summary-grid">
        {items.map(([label, value]) => (
          <div key={label}><dt>{label}</dt><dd>{typeof value === 'number' ? formatMoney(value) : value}</dd></div>
        ))}
        <div className="orc-summary-total">
          <dt>{hhSummary ? 'Total estimado do contrato (HH)' : 'Preço total de faturamento'}</dt>
          <motion.dd key={summary.precoTotalFaturamento} initial={{ opacity: 1 }} animate={reducedMotion ? {} : { opacity: [0.65, 1] }} transition={{ duration: 0.18 }}>{formatMoney(summary.precoTotalFaturamento)}</motion.dd>
        </div>
      </dl>
    </GoFlowWindow>
  );
}

export default function DfpEditor({
  budget,
  catalogo,
  onExport,
  serverError,
  busy,
  canEdit,
  errors,
  form,
  hhSchema,
  onClose,
  onDfpChange,
  onDfpUpdate,
  onHeaderChange,
  onImportHh,
  onSave,
  revision,
  schema,
}) {
  const closeButtonRef = useRef(null);
  const [minimized, setMinimized] = useState(false);
  const [maximized, setMaximized] = useState(true);
  const [importingHh, setImportingHh] = useState(false);
  const isHh = form.modalidade === 'HH';
  const hhDefaults = hhSchema?.defaults;
  const editable = canEdit && !busy;
  // Modalidade HH abre a planilha de composição por Homem-Hora; sem composição salva, uma
  // revisão editável parte do modelo padrão (a planilha de referência) e uma somente leitura
  // não finge ter valores que nunca foram gravados.
  // Revisão que já era HH e tem preço DFP (criada antes da composição HH) não troca de valor
  // sozinha: o modelo de exemplo só entra por ação explícita. Orçamento novo, sem preço DFP, ou
  // que acabou de mudar para HH parte direto do modelo.
  const dfpSalvoTemPreco = useMemo(
    () => computeDfpSummary(revision?.dfp || {}).precoTotalFaturamento > 0,
    [revision],
  );
  const semeiaSozinho = revision?.modalidade !== 'HH' || !dfpSalvoTemPreco;
  const hh = form.dfp?.hh || (canEdit && semeiaSozinho ? hhDefaults : null);
  const carregarModeloHh = () => onDfpChange({ ...form.dfp, hh: JSON.parse(JSON.stringify(hhDefaults)) });
  useEffect(() => {
    if (isHh && canEdit && semeiaSozinho && !form.dfp?.hh && hhDefaults) {
      onDfpChange({ ...form.dfp, hh: JSON.parse(JSON.stringify(hhDefaults)) });
    }
  }, [isHh, canEdit, semeiaSozinho, form.dfp, hhDefaults, onDfpChange]);
  const changeHh = (next) => onDfpChange({ ...form.dfp, hh: next });
  const importHh = async (file) => {
    if (!onImportHh) return;
    setImportingHh(true);
    try {
      const imported = await onImportHh(file);
      // Aplica sobre o estado atual: o usuário pode ter editado o cabeçalho durante o upload.
      if (imported && onDfpUpdate) onDfpUpdate((dfp) => ({ ...dfp, hh: imported }));
      else if (imported) changeHh(imported);
    } finally {
      setImportingHh(false);
    }
  };
  const hhView = useHhSections({
    disabled: !editable,
    hh: hh || hhDefaults,
    importing: importingHh,
    onChange: changeHh,
    onImport: importHh,
    prazoMeses: mesesDoPrazo(form.prazoExecucaoDias),
  });
  const showHh = isHh && Boolean(hh);
  const schemaSections = getSchemaSections(schema);
  const sections = showHh ? hhView.sections : schemaSections;

  const reducedMotion = useReducedMotion();
  const dialogRef = useOrcamentoDialog({ busy, initialFocusRef: closeButtonRef, onClose });
  const formRef = useRef(null);
  const scrollPosition = useRef(0);
  const tableScrollPositions = useRef({});
  const [activeSection, setActiveSection] = useState('orc-section-header');
  const navigation = [
    { id: 'orc-section-header', title: 'Cabeçalho' },
    ...sections.map((section) => ({ id: `orc-section-${section.id}`, title: section.title })),
    { id: 'orc-section-summary', title: 'Impostos e resumo' },
  ];

  const toggleMinimized = () => {
    if (!minimized) {
      scrollPosition.current = formRef.current?.scrollTop || 0;
      const tables = [...(formRef.current?.querySelectorAll('.orc-table-scroll') || [])];
      tableScrollPositions.current = Object.fromEntries(tables.map((table) => [
        table.dataset.scrollKey,
        { left: table.scrollLeft, top: table.scrollTop },
      ]));
    }
    setMinimized((current) => !current);
  };

  useLayoutEffect(() => {
    if (minimized || !formRef.current) return;
    formRef.current.scrollTop = scrollPosition.current;
    formRef.current.querySelectorAll('.orc-table-scroll').forEach((table) => {
      const position = tableScrollPositions.current[table.dataset.scrollKey];
      if (position) {
        table.scrollLeft = position.left;
        table.scrollTop = position.top;
      }
    });
  }, [minimized]);

  useEffect(() => {
    const container = formRef.current;
    if (!container) return undefined;
    const updateActive = () => {
      const top = container.getBoundingClientRect().top;
      const windows = [...container.querySelectorAll('[id^="orc-section-"]')];
      const current = windows.filter((element) => element.getBoundingClientRect().top <= top + 100).at(-1);
      if (current) setActiveSection(current.id);
    };
    container.addEventListener('scroll', updateActive, { passive: true });
    updateActive();
    return () => container.removeEventListener('scroll', updateActive);
  }, [minimized, schema]);

  const navigateTo = (id) => {
    setActiveSection(id);
    const section = document.getElementById(id);
    section?.scrollIntoView({ behavior: reducedMotion ? 'instant' : 'smooth', block: 'start' });
  };

  return (
    <CatalogContext.Provider value={catalogo || {}}>
    <motion.div {...windowMotion(reducedMotion)} className="orc-editor-layer" role="presentation">
      <motion.div
        layout={reducedMotion ? false : "size"}
        transition={{ duration: reducedMotion ? 0 : 0.28 }}
        ref={dialogRef}
        tabIndex={-1}
        aria-describedby="orc-editor-mode"
        aria-label={budget.contratante}
        aria-modal="true"
        className={`orc-editor-dialog ${minimized ? 'is-minimized' : ''} ${maximized ? 'is-maximized' : ''}`}
        role="dialog"
      >
        <GoFlowWindow
          actions={(
            <div className="orc-window-controls">
              <button
                aria-label={minimized ? 'Restaurar editor' : 'Minimizar editor'}
                className="orc-icon-btn"
                onClick={toggleMinimized}
                type="button"
              >
                <Minus aria-hidden="true" />
              </button>
              <button
                aria-label={maximized ? 'Restaurar tamanho do editor' : 'Maximizar editor'}
                className="orc-icon-btn"
                disabled={minimized}
                onClick={() => setMaximized((current) => !current)}
                type="button"
              >
                {maximized ? <Minimize2 aria-hidden="true" /> : <Maximize2 aria-hidden="true" />}
              </button>
              <button
                aria-label="Fechar editor"
                className="orc-icon-btn orc-icon-btn--close"
                disabled={busy}
                onClick={onClose}
                ref={closeButtonRef}
                type="button"
              >
                <X aria-hidden="true" />
              </button>
            </div>
          )}
          className="orc-editor-titlebar"
          eyebrow={`${budget.codigo.replace(/-R\d+$/, '')}-R${revision.numero}`}
          icon={canEdit ? FileText : LockKeyhole}
          title={budget.contratante}
          titleAs="h2"
        >
          <p id="orc-editor-mode">
            {canEdit
              ? 'Composição de preços. As alterações serão gravadas apenas nesta revisão.'
              : 'Histórico em modo somente leitura. Esta revisão permanece preservada.'}
          </p>
        </GoFlowWindow>

        {!minimized && (
            <label className="orc-mobile-nav">
              <span>Seção do orçamento</span>
              <select value={activeSection} onChange={(event) => navigateTo(event.target.value)}>
                {navigation.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
              </select>
            </label>
        )}

        {!minimized && <div className="orc-editor-layout">
          <GoFlowWindow as="nav" className="orc-editor-nav" eyebrow="Seções" icon={BookOpenCheck} title="Formação de preços">
            {navigation.map((item) => (
              <a aria-current={activeSection === item.id ? 'location' : undefined} href={`#${item.id}`} key={item.id}
                onClick={(event) => { event.preventDefault(); navigateTo(item.id); }}>
                {activeSection === item.id && <motion.span aria-hidden="true" className="orc-nav-indicator" layoutId="orc-active-section" transition={{ duration: reducedMotion ? 0 : 0.18 }} />}
                <span className="orc-nav-label">{item.title}</span>
              </a>
            ))}
          </GoFlowWindow>

          <form className="orc-editor-form" onSubmit={onSave} ref={formRef}>
            {serverError && <p className="orc-note" role="alert">{serverError}</p>}
            {showHh && <p className="orc-note orc-note--hh">Modalidade HH: composição por Homem-Hora (salário + encargos, custos mensais por pessoa, BDI e tributos), como na planilha de composição de custos. {!revision?.dfp?.hh && 'Modelo padrão da planilha carregado — ajuste e salve a revisão para gravá-lo.'}</p>}
            {isHh && !showHh && (
              <p className="orc-note">
                Esta revisão está na modalidade HH, mas o preço salvo vem da composição DFP abaixo.{' '}
                {canEdit && hhDefaults && <button className="orc-btn orc-btn--compact" disabled={busy} type="button" onClick={carregarModeloHh}>Iniciar composição HH com o modelo padrão</button>}
              </p>
            )}
            {!showHh && form.dfp?.calculation_version !== 2 && <p className="orc-note">Revisão com regras anteriores à atualização. Seus cálculos históricos foram preservados.</p>}
            {!showHh && form.dfp?.calculation_version === 2 && <p className="orc-note">Perfil de compatibilidade em validação. Confirme dias, mobilização, jornadas, incidência de horas extras e descontos conforme a regra comercial aprovada para este orçamento.</p>}

            <GoFlowWindow eyebrow="Dados contratuais" icon={FileText} id="orc-section-header" title="Cabeçalho">
              <HeaderFields disabled={!canEdit || busy} errors={errors} form={form} onChange={onHeaderChange} onDfpChange={onDfpChange} />
              {errors.dfp && <p className="orc-validation-error" role="alert">{errors.dfp}</p>}
            </GoFlowWindow>

            {showHh && hhView.sections.map((section) => (
              <GoFlowWindow eyebrow={section.eyebrow} icon={Calculator} id={`orc-section-${section.id}`} key={section.id} title={section.title}>
                {section.content}
              </GoFlowWindow>
            ))}

            {!showHh && schemaSections.map((section) => (
              <GoFlowWindow
                eyebrow={{ fields: 'Premissas do orçamento', 'labor-table': 'Equipe e encargos', 'cost-table': 'Composição de custos', 'percent-groups': 'Tributos e margem' }[section.kind] || 'Composição de preços'}
                icon={Calculator}
                id={`orc-section-${section.id}`}
                key={section.id}
                title={section.title}
              >
                <SchemaSection
                  disabled={!canEdit || busy}
                  dfp={form.dfp}
                  onChange={onDfpChange}
                  schema={schema}
                  section={section}
                />
              </GoFlowWindow>
            ))}

            <SummaryWindow dfp={showHh ? { ...form.dfp, hh } : form.dfp} hhSummary={showHh ? hhView.summary : null} prazoDias={form.prazoExecucaoDias} />

            <GoFlowWindow className="orc-editor-footer" title="Finalizar edição">
              <div className="orc-editor-footer__row">
                <p>{canEdit ? 'Revise as premissas antes de salvar.' : 'Esta revisão está disponível somente para consulta.'}</p>
                <div className="orc-button-row">
                  <button className="orc-btn" disabled={busy} onClick={onClose} type="button">Fechar</button>
                  {['docx', 'pdf'].map((format) => <button className="orc-btn" type="button" key={format} onClick={() => onExport?.(format)}>Exportar {format.toUpperCase()} salvo</button>)}
                  {canEdit && (
                    <button className="orc-btn orc-btn--primary" disabled={busy} type="submit">
                      <Save aria-hidden="true" /> Salvar revisão
                    </button>
                  )}
                </div>
              </div>
            </GoFlowWindow>
          </form>
        </div>}
      </motion.div>
    </motion.div>
    </CatalogContext.Provider>
  );
}
