import React, { useContext } from 'react';
import StartDateField from '../StartDateField';
import brazilLocations from '../../../data/brazilLocations.json';
import {
  CAMPOS_REVISAO,
  computeSectionTotal,
  getDfpSectionStatePath,
  getNestedValue,
  updateDfpField,
} from '../../orcamentoModel';
import { CatalogContext, formatMoney, inputValue, typedInputValue } from './editorShared';

const BRAZIL_STATES = brazilLocations.states || [];
const BRAZIL_STATES_BY_CODE = new Map(BRAZIL_STATES.map((state) => [state.code, state]));

export function HeaderFields({ disabled, errors, form, onChange, onDfpChange }) {
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

export function SchemaInput({ disabled, field, label, onChange, options, value }) {
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

export function FieldsSection({ disabled, dfp, onChange, schema, section }) {
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
