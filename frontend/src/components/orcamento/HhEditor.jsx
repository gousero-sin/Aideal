import React, { useMemo, useRef } from 'react';
import { FileSpreadsheet, Plus, Trash2 } from 'lucide-react';
import {
  HH_CUSTO_COLUNAS,
  HH_GRUPOS_ENCARGOS,
  addHhFuncao,
  addHhGrupo,
  computeHhSummary,
  removeHhFuncao,
  removeHhGrupo,
  updateHhBdi,
  updateHhCusto,
  updateHhField,
  updateHhFuncao,
  updateHhGrupo,
  updateHhHoraExtra,
  updateHhPercentItem,
} from './hhModel';

const money = (value) => Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const decimal = (value, digits = 2) => Number(value || 0).toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
const percent = (value) => `${Number(value || 0).toLocaleString('pt-BR', { maximumFractionDigits: 4 })}%`;
const asNumber = (raw) => (raw === '' ? '' : Number(raw));

function NumberCell({ disabled, label, max, onChange, step = '0.01', value }) {
  return (
    <input
      aria-label={label}
      className="orc-num"
      disabled={disabled}
      inputMode="decimal"
      max={max}
      min="0"
      onChange={(event) => onChange(asNumber(event.target.value))}
      step={step}
      type="number"
      value={value ?? ''}
    />
  );
}

function ParamField({ disabled, hint, label, max, onChange, step = '0.01', suffix, value }) {
  return (
    <label className="orc-field">
      <span>{label}</span>
      <span className={suffix ? 'orc-input-suffix' : undefined}>
        <input disabled={disabled} max={max} min="0" onChange={(event) => onChange(asNumber(event.target.value))} step={step} type="number" value={value ?? ''} />
        {suffix && <b>{suffix}</b>}
      </span>
      {hint && <small className="orc-hint">{hint}</small>}
    </label>
  );
}

/** Tabela com rolagem horizontal e coluna de função fixa, no padrão das tabelas do DFP. */
function HhTable({ caption, children, head, footer }) {
  return (
    <div className="orc-table-shell">
      <div className="orc-table-scroll" role="region" aria-label={`${caption}, tabela rolável`} tabIndex={0}>
        <table className="orc-dfp-table orc-hh-table">
          <caption className="orc-visually-hidden">{caption}</caption>
          <thead><tr>{head}</tr></thead>
          <tbody>{children}</tbody>
          {footer && <tfoot>{footer}</tfoot>}
        </table>
      </div>
    </div>
  );
}

function GroupRow({ colSpan, disabled, grupo, hh, onChange, resultado }) {
  return (
    <tr className="orc-hh-group-row">
      <th scope="rowgroup">
        <input aria-label={`Nome do grupo ${grupo.label}`} disabled={disabled} value={grupo.label} onChange={(event) => onChange(updateHhGrupo(hh, grupo.id, event.target.value))} />
      </th>
      <td colSpan={colSpan}>
        <span className="orc-hh-group-meta">{decimal(resultado?.quantidade || 0, 0)} pessoa(s) · {money(resultado?.totalMensal)} / mês</span>
        {!disabled && (
          <span className="orc-hh-group-actions">
            <button className="orc-btn orc-btn--compact" type="button" onClick={() => onChange(addHhFuncao(hh, grupo.id))}><Plus aria-hidden="true" /> Função</button>
            <button className="orc-btn orc-btn--compact" type="button" aria-label={`Remover grupo ${grupo.label}`} onClick={() => onChange(removeHhGrupo(hh, grupo.id))}><Trash2 aria-hidden="true" /> Grupo</button>
          </span>
        )}
      </td>
    </tr>
  );
}

function SalaryTable({ disabled, hh, onChange, summary }) {
  const columns = ['Qtd.', 'Horas / mês', 'Salário base (R$)', 'Periculosidade', 'Adic. noturno (%)', 'Salário / hora', 'Subtotal A¹', `Encargos (${percent(summary.encargos.totalPercent)})`, 'Subtotal A²', 'Total A'];
  return (
    <HhTable
      caption="Equipe e salários"
      head={<><th scope="col">Função</th>{columns.map((label) => <th key={label} scope="col">{label}</th>)}{!disabled && <th scope="col">Ações</th>}</>}
      footer={<tr><th scope="row">Total A · {decimal(summary.colaboradores, 0)} pessoa(s)</th><td colSpan={columns.length - 1} /><td className="orc-num-cell">{money(summary.grupos.reduce((soma, grupo) => soma + grupo.funcoes.reduce((s, linha) => s + linha.totalA, 0), 0))}</td>{!disabled && <td />}</tr>}
    >
      {(hh.grupos || []).map((grupo, gIndex) => (
        <React.Fragment key={grupo.id}>
          <GroupRow colSpan={columns.length + (disabled ? 0 : 1)} disabled={disabled} grupo={grupo} hh={hh} onChange={onChange} resultado={summary.grupos[gIndex]} />
          {(grupo.funcoes || []).map((funcao, fIndex) => {
            const linha = summary.grupos[gIndex]?.funcoes[fIndex] || {};
            const set = (field) => (value) => onChange(updateHhFuncao(hh, grupo.id, funcao.id, field, value));
            return (
              <tr key={funcao.id}>
                <th scope="row"><input aria-label={`Nome da função ${funcao.label}`} disabled={disabled} title={funcao.label} value={funcao.label} onChange={(event) => set('label')(event.target.value)} /></th>
                <td><NumberCell disabled={disabled} label={`${funcao.label} · Quantidade`} onChange={set('quantidade')} step="1" value={funcao.quantidade} /></td>
                <td><NumberCell disabled={disabled} label={`${funcao.label} · Horas por mês`} onChange={set('horas_mes')} value={funcao.horas_mes} /></td>
                <td><NumberCell disabled={disabled} label={`${funcao.label} · Salário base`} onChange={set('salario_base')} value={funcao.salario_base} /></td>
                <td className="orc-check-cell"><input aria-label={`${funcao.label} · Periculosidade de ${percent(hh.periculosidade_percent)}`} checked={Boolean(funcao.periculosidade)} disabled={disabled} type="checkbox" onChange={(event) => set('periculosidade')(event.target.checked)} /> <span>{percent(hh.periculosidade_percent)}</span></td>
                <td><NumberCell disabled={disabled} label={`${funcao.label} · Adicional noturno`} max="99.99" onChange={set('adicional_noturno_percent')} value={funcao.adicional_noturno_percent} /></td>
                <td className="orc-num-cell">{money(linha.salarioHora)}</td>
                <td className="orc-num-cell">{money(linha.subtotalA1)}</td>
                <td className="orc-num-cell">{money(linha.encargosValor)}</td>
                <td className="orc-num-cell">{money(linha.subtotalA2)}</td>
                <td className="orc-num-cell orc-num-cell--strong">{money(linha.totalA)}</td>
                {!disabled && <td><button className="orc-btn orc-btn--compact" type="button" aria-label={`Remover função ${funcao.label}`} onClick={() => onChange(removeHhFuncao(hh, grupo.id, funcao.id))}>Remover</button></td>}
              </tr>
            );
          })}
        </React.Fragment>
      ))}
    </HhTable>
  );
}

function CostsTable({ disabled, hh, onChange, summary }) {
  return (
    <HhTable
      caption="Custos mensais por pessoa"
      head={<><th scope="col">Função</th>{HH_CUSTO_COLUNAS.map((coluna) => <th key={coluna.id} scope="col" title={coluna.baseHoraExtra ? 'Entra na base da hora extra' : 'Fica fora da base da hora extra'}>{coluna.label}{!coluna.baseHoraExtra && <sup aria-hidden="true">*</sup>}</th>)}<th scope="col">Subtotal B</th><th scope="col">Total B</th></>}
      footer={<tr><th scope="row">Total B</th><td colSpan={HH_CUSTO_COLUNAS.length + 1} /><td className="orc-num-cell">{money(summary.grupos.reduce((soma, grupo) => soma + grupo.funcoes.reduce((s, linha) => s + linha.totalB, 0), 0))}</td></tr>}
    >
      {(hh.grupos || []).map((grupo, gIndex) => (grupo.funcoes || []).map((funcao, fIndex) => {
        const linha = summary.grupos[gIndex]?.funcoes[fIndex] || {};
        return (
          <tr key={funcao.id}>
            <th scope="row"><span className="orc-row-label" title={funcao.label}>{funcao.label}</span></th>
            {HH_CUSTO_COLUNAS.map((coluna) => (
              <td key={coluna.id}><NumberCell disabled={disabled} label={`${funcao.label} · ${coluna.label}`} onChange={(value) => onChange(updateHhCusto(hh, grupo.id, funcao.id, coluna.id, value))} value={funcao.custos?.[coluna.id]} /></td>
            ))}
            <td className="orc-num-cell">{money(linha.subtotalB)}</td>
            <td className="orc-num-cell orc-num-cell--strong">{money(linha.totalB)}</td>
          </tr>
        );
      }))}
    </HhTable>
  );
}

function PriceTable({ hh, summary }) {
  const meses = decimal(summary.meses, Number.isInteger(summary.meses) ? 0 : 2);
  return (
    <HhTable
      caption="Formação do preço por função"
      head={<><th scope="col">Função</th>{['Desp. indiretas (C)', 'Lucro (C)', 'Subtotal C', ...(hh.tributos || []).map((item) => `${item.label} (D)`), 'Subtotal D', 'Total unitário / mês', 'Total da função / mês', `Total ${meses} meses`].map((label) => <th key={label} scope="col">{label}</th>)}</>}
      footer={<tr><th scope="row">Total do contrato</th><td colSpan={(hh.tributos || []).length + 5} /><td className="orc-num-cell orc-num-cell--strong">{money(summary.totalMensal)}</td><td className="orc-num-cell orc-num-cell--strong">{money(summary.totalEstimado)}</td></tr>}
    >
      {(hh.grupos || []).map((grupo, gIndex) => (grupo.funcoes || []).map((funcao, fIndex) => {
        const linha = summary.grupos[gIndex]?.funcoes[fIndex] || {};
        return (
          <tr key={funcao.id}>
            <th scope="row"><span className="orc-row-label" title={funcao.label}>{funcao.label}</span></th>
            <td className="orc-num-cell">{money(linha.despesas)}</td>
            <td className="orc-num-cell">{money(linha.lucro)}</td>
            <td className="orc-num-cell">{money(linha.subtotalC)}</td>
            {(hh.tributos || []).map((item) => <td className="orc-num-cell" key={item.id}>{money(linha.tributos?.[item.id])}</td>)}
            <td className="orc-num-cell">{money(linha.subtotalD)}</td>
            <td className="orc-num-cell">{money(linha.unitario)}</td>
            <td className="orc-num-cell">{money(linha.totalMensal)}</td>
            <td className="orc-num-cell orc-num-cell--strong">{money(linha.totalEstimado)}</td>
          </tr>
        );
      }))}
    </HhTable>
  );
}

function RatesTable({ hh, summary }) {
  const he = hh.horas_extras_percentuais || [60, 80, 100];
  const noturno = percent(hh.percentual_noturno);
  return (
    <HhTable
      caption="Valores de Homem-Hora"
      head={<><th scope="col">Função</th><th scope="col">H. normal</th>{he.map((valor, index) => <th key={`d${index}`} scope="col">H. {percent(valor)}</th>)}<th scope="col">Adic. noturno ({noturno})</th><th scope="col">H. noturna</th>{he.map((valor, index) => <th key={`n${index}`} scope="col">H. noturna {percent(valor)}</th>)}</>}
    >
      {(hh.grupos || []).map((grupo, gIndex) => (grupo.funcoes || []).map((funcao, fIndex) => {
        const linha = summary.grupos[gIndex]?.funcoes[fIndex] || {};
        return (
          <tr key={funcao.id}>
            <th scope="row"><span className="orc-row-label" title={funcao.label}>{funcao.label}</span></th>
            <td className="orc-num-cell orc-num-cell--strong">{money(linha.horaNormal)}</td>
            {(linha.horasExtras || []).map((valor, index) => <td className="orc-num-cell" key={`d${index}`}>{money(valor)}</td>)}
            <td className="orc-num-cell">{money(linha.adicionalNoturnoHora)}</td>
            <td className="orc-num-cell">{money(linha.horaNoturna)}</td>
            {(linha.horasExtrasNoturnas || []).map((valor, index) => <td className="orc-num-cell" key={`n${index}`}>{money(valor)}</td>)}
          </tr>
        );
      }))}
    </HhTable>
  );
}

function EncargosSection({ disabled, hh, onChange, summary }) {
  const { grupos, derivados, totalPercent } = summary.encargos;
  return (
    <div className="orc-percent-layout orc-hh-encargos">
      {HH_GRUPOS_ENCARGOS.map(([grupo, titulo]) => (
        <fieldset className="orc-percent-group" key={grupo}>
          <legend>{titulo} · {percent(grupos[grupo])}</legend>
          {(hh.encargos || []).filter((item) => item.grupo === grupo).map((item) => (
            <label className="orc-field orc-field--inline" key={item.id}>
              <span>{item.label}</span>
              <span className="orc-input-suffix"><input aria-label={`Encargo ${item.label}`} disabled={disabled} max="99.99" min="0" step="0.0001" type="number" value={item.percent ?? ''} onChange={(event) => onChange(updateHhPercentItem(hh, 'encargos', item.id, asNumber(event.target.value)))} /><b>%</b></span>
            </label>
          ))}
          {grupo === 'D' && (
            <>
              <p className="orc-hh-derived"><span>Grupo A sobre o Grupo B</span><strong>{percent(derivados.d1)}</strong></p>
              <p className="orc-hh-derived"><span>FGTS (A.2) sobre aviso prévio (C.3)</span><strong>{percent(derivados.d3)}</strong></p>
            </>
          )}
        </fieldset>
      ))}
      <p className="orc-hh-total-line">Total de encargos sociais (A + B + C + D): <strong>{percent(totalPercent)}</strong></p>
    </div>
  );
}

function BdiSection({ disabled, hh, onChange }) {
  const totalTributos = (hh.tributos || []).reduce((soma, item) => soma + Number(item.percent || 0), 0);
  return (
    <div className="orc-percent-layout">
      <fieldset className="orc-percent-group orc-percent-group--accent">
        <legend>BDI sobre (A + B)</legend>
        <ParamField disabled={disabled} label="Despesas administrativas / indiretas" max="99.99" onChange={(value) => onChange(updateHhBdi(hh, 'despesas_indiretas_percent', value))} suffix="%" value={hh.bdi?.despesas_indiretas_percent} />
        <ParamField disabled={disabled} label="Lucro" max="99.99" onChange={(value) => onChange(updateHhBdi(hh, 'lucro_percent', value))} suffix="%" value={hh.bdi?.lucro_percent} />
      </fieldset>
      <fieldset className="orc-percent-group">
        <legend>Tributos sobre (A + B + C) · {percent(totalTributos)}</legend>
        {(hh.tributos || []).map((item) => (
          <ParamField disabled={disabled} key={item.id} label={item.label} max="99.99" onChange={(value) => onChange(updateHhPercentItem(hh, 'tributos', item.id, value))} suffix="%" value={item.percent} />
        ))}
      </fieldset>
    </div>
  );
}

function ParamsSection({ disabled, hh, onChange, onImport, importing, prazoMeses }) {
  const fileRef = useRef(null);
  const he = hh.horas_extras_percentuais || [60, 80, 100];
  return (
    <div className="orc-section-stack">
      <div className="orc-field-grid">
        <ParamField disabled={disabled} hint={prazoMeses ? `Prazo de execução do cabeçalho ≈ ${prazoMeses} mês(es).` : 'Multiplica o total mensal para o total do contrato.'} label="Prazo do contrato (meses)" max="1200" onChange={(value) => onChange(updateHhField(hh, 'meses', value))} step="1" value={hh.meses} />
        <ParamField disabled={disabled} label="Adicional noturno (hora noturna)" max="99.99" onChange={(value) => onChange(updateHhField(hh, 'percentual_noturno', value))} suffix="%" value={hh.percentual_noturno} />
        <ParamField disabled={disabled} label="Periculosidade" max="99.99" onChange={(value) => onChange(updateHhField(hh, 'periculosidade_percent', value))} suffix="%" value={hh.periculosidade_percent} />
        <ParamField disabled={disabled} hint="Referência; não entra no cálculo." label="Salário mínimo (R$)" onChange={(value) => onChange(updateHhField(hh, 'salario_minimo', value))} value={hh.salario_minimo} />
        {he.map((valor, index) => (
          <ParamField disabled={disabled} key={index} label={`Hora extra ${index + 1}`} max="1000" onChange={(value) => onChange(updateHhHoraExtra(hh, index, value))} suffix="%" value={valor} />
        ))}
      </div>
      {!disabled && (
        <div className="orc-table-actions">
          <input accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" className="orc-visually-hidden" ref={fileRef} tabIndex={-1} type="file" onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ''; if (file) onImport(file); }} />
          <button className="orc-btn" disabled={importing} type="button" onClick={() => fileRef.current?.click()}><FileSpreadsheet aria-hidden="true" /> {importing ? 'Importando planilha…' : 'Importar planilha de composição (.xlsx)'}</button>
          <button className="orc-btn" type="button" onClick={() => onChange(addHhGrupo(hh))}><Plus aria-hidden="true" /> Adicionar grupo de funções</button>
        </div>
      )}
    </div>
  );
}

/**
 * Seções da composição HH. Devolve a lista para o editor montar janelas e navegação, igual às
 * seções do DFP; `hh` já vem semeado com o modelo padrão quando a revisão ainda não tem um.
 */
export function useHhSections({ disabled, hh, importing, onChange, onImport, prazoMeses }) {
  const summary = useMemo(() => computeHhSummary(hh), [hh]);
  const props = { disabled, hh, onChange, summary };
  return {
    summary,
    sections: [
      { id: 'hh-parametros', title: 'Parâmetros HH', eyebrow: 'Premissas do contrato', content: <ParamsSection {...props} importing={importing} onImport={onImport} prazoMeses={prazoMeses} /> },
      { id: 'hh-salarios', title: 'Equipe e salários (A)', eyebrow: 'Salário, adicionais e encargos', content: <SalaryTable {...props} /> },
      { id: 'hh-custos', title: 'Custos mensais por pessoa (B)', eyebrow: '* fora da base da hora extra', content: <CostsTable {...props} /> },
      { id: 'hh-encargos', title: 'Encargos sociais', eyebrow: 'Composição dos encargos', content: <EncargosSection {...props} /> },
      { id: 'hh-bdi', title: 'BDI e tributos (C e D)', eyebrow: 'Margem e impostos', content: <BdiSection {...props} /> },
      { id: 'hh-preco', title: 'Formação do preço', eyebrow: 'Total por função e contrato', content: <PriceTable {...props} /> },
      { id: 'hh-valores', title: 'Valores de Homem-Hora', eyebrow: 'Hora normal, extra e noturna', content: <RatesTable {...props} /> },
    ],
  };
}
