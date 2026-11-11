import { createContext } from 'react';
import { INHERITED_LABOR_DAYS } from '../../orcamentoModel';

export const formatMoney = (value) => Number(value || 0).toLocaleString('pt-BR', {
  style: 'currency',
  currency: 'BRL',
});
export const formatPercent = (value) => `${Number(value || 0).toLocaleString('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})}%`;
// Valores calculados (hora, horas trabalhadas) chegam com dízimas; o campo é só leitura.
export const COMPUTED_LABOR_COLUMNS = new Set(['worked_hours', 'hourly_rate']);
export const roundComputed = (value) => (Number.isFinite(Number(value)) ? Math.round(Number(value) * 100) / 100 : value);

export const inputValue = (value) => value ?? '';
export const CatalogContext = createContext({ funcoes: [], itens: [], custo_administrativo_diario: 0 });
export const NATURAL_LABOR_COLUMNS = new Set(['quantity', 'worked_days', 'saturday_days', 'sunday_days', 'mobilization_days']);
export const INHERITED_LABOR_COLUMNS = new Set(Object.keys(INHERITED_LABOR_DAYS));
export const HIDDEN_V2_LABOR_COLUMNS = new Set(['hours_per_employee', 'salary_base_hours', 'manual_total']);
export const typedInputValue = (type, value) => (
  type === 'number' && value !== '' ? Number(value) : value
);
