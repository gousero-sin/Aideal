import React, { useId } from 'react';

// Mesma anatomia dos outros campos (.orc-field: rótulo, controle, mensagem), com o N/A ao lado.
export default function StartDateField({ value, disabled, onChange, error }) {
  const id = useId();
  const notDefined = value === 'N/A';
  const errorId = `${id}-error`;
  return (
    <div className="orc-field orc-field--date">
      <span aria-hidden="true">Data de início</span>
      <div className="orc-date-row">
        <input
          aria-describedby={error ? errorId : undefined}
          aria-invalid={Boolean(error)}
          aria-label="Data de início"
          disabled={disabled || notDefined}
          onChange={(event) => onChange(event.target.value)}
          type="date"
          value={notDefined ? '' : value || ''}
        />
        <label className="orc-check orc-check--inline">
          <input checked={notDefined} disabled={disabled} onChange={(event) => onChange(event.target.checked ? 'N/A' : '')} type="checkbox" />
          <span>N/A — início não definido</span>
        </label>
      </div>
      {error && <small id={errorId} role="alert">{error}</small>}
    </div>
  );
}
