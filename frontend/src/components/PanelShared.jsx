import React, { useEffect } from 'react';
import { ChevronDown, CheckCircle2, Database, Download, FileCheck2, SearchCheck } from 'lucide-react';
import { GlacierGlassCard } from 'goflow-core';

export function PanelHero({ kicker, title, description, meta = [], actions }) {
  return (
    <GlacierGlassCard className="aideal-page-hero-card">
      <div className="aideal-page-hero-content">
        <div className="aideal-page-hero-copy">
          <span className="aideal-page-kicker">{kicker}</span>
          <h2>{title}</h2>
          <p>{description}</p>
          {meta.length > 0 && (
            <div className="aideal-page-meta" aria-label="Resumo do painel">
              {meta.map((item) => (
                <span key={`${item.label}-${item.value}`}>
                  <strong>{item.label}</strong>
                  {item.value}
                </span>
              ))}
            </div>
          )}
        </div>
        {actions && <div className="aideal-page-actions">{actions}</div>}
      </div>
    </GlacierGlassCard>
  );
}

export function KpiCard({ label, value, tone = 'blue', icon, detail }) {
  return (
    <div className={`aideal-insight-kpi aideal-insight-kpi-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
      {icon && <em>{icon}</em>}
    </div>
  );
}

export function SituationGrid({ items }) {
  const visibleItems = Array.isArray(items) ? items.filter(Boolean) : [];
  if (visibleItems.length === 0) return null;

  return (
    <section className="aideal-situation-grid" aria-label="Situações relevantes">
      {visibleItems.map((item) => (
        <article key={item.label} className={`aideal-situation-card is-${item.tone || 'blue'}`}>
          <span>{item.label}</span>
          <strong>{item.value || '-'}</strong>
          {item.helper && <p>{item.helper}</p>}
        </article>
      ))}
    </section>
  );
}

export function RecentActivityCard({
  title,
  subtitle,
  rows,
  emptyText,
  getPrimary,
  getMeta,
  getAmount,
  getTone,
}) {
  const records = Array.isArray(rows) ? rows : [];

  return (
    <article className="aideal-data-card">
      <div className="aideal-chart-heading">
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </div>
      <div className="aideal-table-list">
        {records.length === 0 ? (
          <span className="aideal-chart-empty">{emptyText}</span>
        ) : (
          records.map((item) => (
            <div key={item.id} className="aideal-table-row">
              <div>
                <strong title={getPrimary(item)}>{getPrimary(item)}</strong>
                <span title={getMeta(item)}>{getMeta(item)}</span>
              </div>
              <em className={getTone(item)}>{getAmount(item)}</em>
            </div>
          ))
        )}
      </div>
    </article>
  );
}

export function FinancialHealthCard({ title, subtitle, headline, metrics = [] }) {
  const visibleMetrics = Array.isArray(metrics) ? metrics.filter(Boolean) : [];

  return (
    <article className="aideal-data-card aideal-health-card">
      <div className="aideal-chart-heading">
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </div>

      {headline && (
        <div className={`aideal-health-hero is-${headline.tone || 'cyan'}`}>
          <span>{headline.label}</span>
          <strong>{headline.value}</strong>
          {headline.detail && <p>{headline.detail}</p>}
        </div>
      )}

      <div className="aideal-health-metrics">
        {visibleMetrics.map((metric) => {
          const progress = Math.min(100, Math.max(0, Number(metric.progress || 0)));
          return (
            <div key={metric.label} className={`aideal-health-metric is-${metric.tone || 'blue'}`}>
              <div>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
              </div>
              {metric.detail && <em>{metric.detail}</em>}
              {metric.progress !== undefined && (
                <span className="aideal-health-meter" style={{ '--aideal-health-fill': `${progress}%` }}>
                  <i />
                </span>
              )}
            </div>
          );
        })}
      </div>
    </article>
  );
}

export function PanelSkeleton() {
  return (
    <GlacierGlassCard className="aideal-dashboard-card aideal-panel-skeleton">
      <span className="aideal-skeleton-line is-short" />
      <span className="aideal-skeleton-line is-wide" />
      <span className="aideal-skeleton-line is-medium" />
    </GlacierGlassCard>
  );
}

export function OperationSection({
  title,
  description,
  icon,
  open,
  onOpenChange,
  busy,
  hasResults,
  children,
}) {
  useEffect(() => {
    if ((busy || hasResults) && !open) {
      onOpenChange?.(true);
    }
  }, [busy, hasResults, onOpenChange, open]);

  const steps = [
    { label: 'Detectar', icon: <SearchCheck size={14} aria-hidden="true" /> },
    { label: 'Validar', icon: <FileCheck2 size={14} aria-hidden="true" /> },
    { label: 'Salvar', icon: <Database size={14} aria-hidden="true" /> },
    { label: 'Gerar', icon: <CheckCircle2 size={14} aria-hidden="true" /> },
    { label: 'Baixar', icon: <Download size={14} aria-hidden="true" /> },
  ];

  return (
    <section className={`aideal-operation-band ${open ? 'is-open' : ''}`}>
      <div className="aideal-operation-summary">
        <div>
          <h2>
            {icon}
            {title}
          </h2>
          <p>{description}</p>
        </div>
        <button
          className="aideal-action aideal-action-secondary"
          type="button"
          onClick={() => onOpenChange?.(!open)}
          aria-expanded={open}
        >
          <span>{open ? 'Recolher operação' : 'Abrir operação'}</span>
          <ChevronDown size={16} aria-hidden="true" />
        </button>
      </div>
      <div className="aideal-operation-steps" aria-label="Etapas da operação">
        {steps.map((step) => (
          <span key={step.label} className={busy ? 'is-busy' : ''}>
            {step.icon}
            {step.label}
          </span>
        ))}
      </div>
      {open && <div className="aideal-operation-body">{children}</div>}
    </section>
  );
}
