import React, { useContext } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { Plus, Trash2 } from 'lucide-react';
import { listItemMotion } from '../orcamentoMotion';
import {
  computeDfpSummary,
  computeLaborRow,
  computeSectionTotal,
  computeTableRowSubtotal,
  createDfpItemId,
  getDfpSectionStatePath,
  getNestedValue,
  inheritedLaborDays,
  nextDfpItemLabel,
  removeDfpCollectionItem,
  setNestedValue,
  updateDfpCollectionItemAtPath,
  updateDfpField,
} from '../../orcamentoModel';
import TableScroll from './TableScroll';
import { SchemaInput } from './FieldInputs';
import {
  CatalogContext,
  COMPUTED_LABOR_COLUMNS,
  formatMoney,
  formatPercent,
  HIDDEN_V2_LABOR_COLUMNS,
  INHERITED_LABOR_COLUMNS,
  inputValue,
  NATURAL_LABOR_COLUMNS,
  roundComputed,
  typedInputValue,
} from './editorShared';

const DEFAULT_EMPTY_DAYS = new Set(['worked_days', 'saturday_days', 'sunday_days']);

const newRow = (columns, items) => ({
  ...Object.fromEntries(columns.map((column) => [
    column.key,
    DEFAULT_EMPTY_DAYS.has(column.key) ? null : column.type === 'number' ? 0 : '',
  ])),
  id: createDfpItemId(),
  label: nextDfpItemLabel(items),
});

/** Tabela de itens do DFP (mão de obra e composições de custo). */
export function DfpTable({ collectionPath, columns, disabled, dfp, onChange, sectionTitle }) {
  const catalog = useContext(CatalogContext);
  const reducedMotion = useReducedMotion();
  const isLabor = collectionPath.startsWith('mao_de_obra');
  const suggestions = isLabor ? catalog.funcoes || [] : catalog.itens || [];
  const listId = `catalog-${collectionPath.replaceAll('.', '-')}`;
  const items = getNestedValue(dfp, collectionPath);
  const rows = Array.isArray(items) ? items : [];
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
      isLabor ? 'salary_real' : 'unit_cost', suggestion.salario_real ?? suggestion.valor_unitario) : changed);
  };
  const cellValue = (item, column) => {
    if (dfp.calculation_version === 2 && collectionPath === 'alimentacao.items' && column.key === 'quantity') return peopleDays;
    if (!isUpdatedLabor) return item[column.key];
    const computed = computeLaborRow(item, dfp)[column.key];
    return COMPUTED_LABOR_COLUMNS.has(column.key) ? roundComputed(computed) : computed;
  };

  return (
    <div className="orc-table-shell">
      <TableScroll label={sectionTitle} scrollKey={collectionPath}>
        <datalist id={listId}>{suggestions.map((entry) => <option key={entry.nome} value={entry.nome} />)}</datalist>
        <table className="orc-dfp-table">
          <thead>
            <tr>
              <th scope="col">Item</th>
              {visibleColumns.map((column) => <th key={column.key} scope="col">{column.label}</th>)}
              <th scope="col">{isLabor ? 'Subtotal antes de adicionais e encargos' : 'Subtotal'}</th>
              {canRemoveRows && <th scope="col">Ações</th>}
            </tr>
          </thead>
          <tbody>
            <AnimatePresence initial={false}>
              {rows.map((item) => (
                <motion.tr key={item.id} {...listItemMotion(reducedMotion)}>
                  <th scope="row"><input list={listId} aria-label={`${sectionTitle} · Nome do item ${item.id}`} disabled={disabled} title={item.label} value={item.label} onChange={(event) => changeName(item, event.target.value)} /></th>
                  {visibleColumns.map((column) => {
                    const inherited = isUpdatedLabor && INHERITED_LABOR_COLUMNS.has(column.key);
                    return (
                      <td key={column.key}>
                        <input
                          aria-label={`${sectionTitle} · ${item.label} · ${column.label}`}
                          className={column.type === 'number' ? 'orc-num' : undefined}
                          disabled={disabled}
                          readOnly={column.readonly || column.read_only || (isUpdatedLabor && COMPUTED_LABOR_COLUMNS.has(column.key))}
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
                          placeholder={inherited ? String(inheritedLaborDays(dfp, column.key)) : undefined}
                          title={inherited
                            ? `Em branco usa ${inheritedLaborDays(dfp, column.key)}, o valor de Identificação e Escopo. Digite 0 para não considerar.`
                            : undefined}
                          value={inputValue(cellValue(item, column))}
                        />
                      </td>
                    );
                  })}
                  <td className="orc-num-cell">{formatMoney(computeTableRowSubtotal(dfp, collectionPath, item))}</td>
                  {canRemoveRows && <td><button className="orc-btn orc-btn--compact" type="button" aria-label={`Remover ${sectionTitle} · ${item.label}`} onClick={() => onChange(removeDfpCollectionItem(dfp, collectionPath, item.id))}><Trash2 aria-hidden="true" />Remover</button></td>}
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
          {/* O valor fica na coluna fixa: na última coluna ele some atrás da rolagem horizontal. */}
          <tfoot><tr><th scope="row" className="orc-table-total"><span>Total</span><strong>{formatMoney(total)}</strong><small>{formatPercent(directTotal ? (100 * total) / directTotal : 0)} dos custos diretos</small></th><td colSpan={visibleColumns.length} /><td className="orc-num-cell orc-num-cell--strong">{formatMoney(total)}</td>{canRemoveRows && <td />}</tr></tfoot>
        </table>
        {rows.length === 0 && <p className="orc-table-empty">Nenhum item lançado em {sectionTitle}.</p>}
      </TableScroll>
      <div className="orc-table-actions">
        <button type="button" className="orc-btn" disabled={disabled} onClick={() => onChange(setNestedValue(dfp, collectionPath, [...rows, newRow(visibleColumns, items)]))}><Plus aria-hidden="true" />Adicionar item</button>
        {dfp.calculation_version === 2 && <label className="orc-field">Desconto do subtópico (%)<input type="number" min="0" max="100" step="0.01" disabled={disabled} value={getNestedValue(dfp, `${sectionPath}.discount_percent`) || 0} onChange={(event) => onChange(updateDfpField(dfp, sectionPath, 'discount_percent', Number(event.target.value)))} /></label>}
      </div>
    </div>
  );
}

export function LaborSection({ disabled, dfp, onChange, section }) {
  const statePath = getDfpSectionStatePath(section);
  const adjustments = getNestedValue(dfp, `${statePath}.adjustments`) || [];
  const footer = section.footer_field;
  return (
    <div className="orc-section-stack">
      <DfpTable
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

export function CostSection({ disabled, dfp, onChange, section }) {
  const path = getDfpSectionStatePath(section);
  const collectionPath = Array.isArray(getNestedValue(dfp, path)) ? path : `${path}.items`;
  return (
    <DfpTable
      collectionPath={collectionPath}
      columns={section.columns || []}
      disabled={disabled}
      dfp={dfp}
      onChange={onChange}
      sectionTitle={section.title}
    />
  );
}
