import React from 'react';

export default function StartDateField({ value, disabled, onChange, error }) {
  return <div className="orc-field">
    <label>Data de início<input aria-label="Data de início" type="date" disabled={disabled || value === 'N/A'}
      value={value === 'N/A' ? '' : value || ''} onChange={(e) => onChange(e.target.value)} /></label>
    <label className="orc-check"><input type="checkbox" disabled={disabled} checked={value === 'N/A'}
      onChange={(e) => onChange(e.target.checked ? 'N/A' : '')} />N/A — início não definido</label>
    {error && <small role="alert">{error}</small>}
  </div>;
}
