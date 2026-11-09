import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  addHhFuncao,
  addHhGrupo,
  collectHhWarnings,
  computeHhEncargos,
  computeHhFuncao,
  computeHhSummary,
  mesesDoPrazo,
  removeHhFuncao,
  updateHhCusto,
  updateHhFuncao,
  validateHh,
} from './orcamento/hhModel.js';
import { avisosDePrazo, buildOrcamentoPayload, validateRevisaoForm } from './orcamentoModel.js';

// Mesmo modelo que o backend entrega em /schema (drift coberto por test_orcamento_hh.py).
const modelo = () => JSON.parse(readFileSync(new URL('./__fixtures__/hhModeloPadrao.json', import.meta.url), 'utf8'));
const cents = (value) => Math.round((value + 1e-9) * 100) / 100;

test('HH reproduz a planilha de composição célula a célula', () => {
  const hh = modelo();
  const encarregado = computeHhFuncao(hh.grupos[0].funcoes[0], hh);
  assert.equal(cents(encarregado.unitario), 17118.56); // BJ8
  assert.equal(cents(encarregado.subtotalA2), 10736.49); // P8
  assert.equal(cents(encarregado.subtotalB), 3119.93); // AM8
  assert.equal(cents(encarregado.subtotalC), 859.1); // AT8
  assert.equal(cents(encarregado.subtotalD), 2403.04); // BG8
  assert.equal(cents(encarregado.horaNormal), 77.81); // BP8
  assert.deepEqual(encarregado.horasExtras.map(cents), [103.24, 116.14, 129.04]); // BQ..BS
  assert.equal(cents(encarregado.adicionalNoturnoHora), 15.56); // BT8
  assert.equal(cents(encarregado.horaNoturna), 93.37); // BU8
  assert.deepEqual(encarregado.horasExtrasNoturnas.map(cents), [123.88, 139.37, 154.85]); // BV..BX
  const resumo = computeHhSummary(hh);
  assert.equal(resumo.grupos[0].totalEstimado, 2622557.13); // BN12
  assert.equal(resumo.grupos[1].totalEstimado, 1757495.85); // BN16
  assert.equal(resumo.totalEstimado, 4380052.98);
  assert.equal(resumo.precoTotalFaturamento, 4380052.98);
  assert.equal(resumo.colaboradores, 10);
});

test('HH: resumo bate com o backend (compute_hh_summary do modelo padrão)', () => {
  const resumo = computeHhSummary(modelo());
  assert.equal(resumo.custosDiretosTotal, 3545382.68);
  assert.equal(resumo.custosIndiretosTotal, 77998.42);
  assert.equal(resumo.lucroTotal, 141815.31);
  assert.equal(resumo.custosTotais, 3765196.4);
  assert.equal(resumo.totalMensal, 121668.14);
  assert.ok(Math.abs(resumo.aliquotaImpostosTotal - 16.33) < 1e-9);
});

test('HH: encargos somam 125,57586% com o grupo D derivado', () => {
  const encargos = computeHhEncargos(modelo());
  assert.ok(Math.abs(encargos.totalPercent - 125.57586) < 1e-9);
  assert.ok(Math.abs(encargos.derivados.d1 - 14.80626) < 1e-9);
  assert.ok(Math.abs(encargos.derivados.d3 - 1.0496) < 1e-9);
});

test('HH: periculosidade, noturno e horas zeradas', () => {
  const hh = modelo();
  const funcao = { ...hh.grupos[0].funcoes[0], salario_base: 1000, periculosidade: true, adicional_noturno_percent: 20 };
  const linha = computeHhFuncao(funcao, hh);
  assert.equal(linha.periculosidade, 300);
  assert.equal(linha.adicionalNoturno, 200);
  assert.equal(linha.subtotalA1, 1500);
  const semHoras = computeHhFuncao({ ...funcao, horas_mes: 0 }, hh);
  assert.equal(semHoras.horaNormal, 0);
  assert.deepEqual(semHoras.horasExtras, [0, 0, 0]);
});

test('HH: edições são imutáveis e mantêm ids únicos', () => {
  const hh = modelo();
  const original = JSON.stringify(hh);
  const comGrupo = addHhGrupo(hh);
  const grupoId = comGrupo.grupos.at(-1).id;
  const comFuncao = addHhFuncao(addHhFuncao(comGrupo, grupoId), grupoId);
  const ids = comFuncao.grupos.flatMap((grupo) => grupo.funcoes.map((funcao) => funcao.id));
  assert.equal(new Set(ids).size, ids.length);
  const funcaoId = comFuncao.grupos.at(-1).funcoes[0].id;
  const editado = updateHhCusto(updateHhFuncao(comFuncao, grupoId, funcaoId, 'salario_base', 3000), grupoId, funcaoId, 'epi', 50);
  assert.equal(editado.grupos.at(-1).funcoes[0].salario_base, 3000);
  assert.equal(editado.grupos.at(-1).funcoes[0].custos.epi, 50);
  assert.equal(removeHhFuncao(editado, grupoId, funcaoId).grupos.at(-1).funcoes.length, 1);
  assert.equal(JSON.stringify(hh), original);
});

test('HH: validação bloqueia o que o backend recusaria e avisa totais zerados', () => {
  const hh = modelo();
  assert.deepEqual(validateHh(hh), []);
  const tributos = { ...hh, tributos: hh.tributos.map((item) => ({ ...item, percent: 30 })) };
  assert.match(validateHh(tributos).join(' '), /soma dos tributos/);
  const negativo = updateHhFuncao(hh, hh.grupos[0].id, hh.grupos[0].funcoes[0].id, 'salario_base', -5);
  assert.match(validateHh(negativo).join(' '), /entre 0 e 1 bilhão/);
  const semNome = updateHhFuncao(hh, hh.grupos[0].id, hh.grupos[0].funcoes[0].id, 'label', ' ');
  assert.match(validateHh(semNome).join(' '), /nome/);
  assert.match(collectHhWarnings({ ...hh, meses: 0 }).join(' '), /meses está zerado/);
  const form = { modalidade: 'HH', prazoExecucaoDias: '', dataInicio: '', dfp: { calculation_version: 2, hh: tributos } };
  assert.match(validateRevisaoForm(form).dfp, /soma dos tributos/);
  // O bloco HH continua salvo fora da modalidade HH e o backend o valida: o front também.
  assert.match(validateRevisaoForm({ ...form, modalidade: 'Spot' }).dfp, /soma dos tributos/);
  assert.equal(validateRevisaoForm({ ...form, dfp: { calculation_version: 2, hh: modelo() } }).dfp, undefined);
});

test('HH: criar orçamento em HH já envia o modelo padrão', () => {
  const form = { contratante: 'Cliente', modalidade: 'HH', prazoExecucaoDias: '', dataInicio: '', dfp: { calculation_version: 2, metadata: {} } };
  assert.deepEqual(buildOrcamentoPayload(form, { hhDefaults: modelo() }).dfp.hh, modelo());
  assert.equal(buildOrcamentoPayload({ ...form, modalidade: 'Spot' }, { hhDefaults: modelo() }).dfp.hh, undefined);
  assert.equal(mesesDoPrazo('1095'), 37);
  assert.equal(mesesDoPrazo(''), null);
});

const dfpComPrazo = (metadata, items) => ({
  calculation_version: 2,
  metadata: { quantidade_dias_semana: 0, quantidade_sabado: 0, quantidade_domingo: 0, ...metadata },
  mao_de_obra_direta: { items },
});

test('aviso: prazo do cabeçalho diferente dos dias usados na mão de obra (caso ORC-0001)', () => {
  const dfp = dfpComPrazo(
    { prazo_execucao_text: '45', quantidade_dias_semana: 260, quantidade_sabado: 53, quantidade_domingo: 52 },
    [{ id: 'a', label: 'Pintor', quantity: 1, mobilization_days: 10, worked_days: null, saturday_days: null, sunday_days: null }],
  );
  const avisos = avisosDePrazo(dfp, '45');
  assert.equal(avisos.length, 1);
  assert.match(avisos[0], /45 dias.*365 dias/);
});

test('aviso: dias de execução zerados contam só a mobilização (caso ORC-0003)', () => {
  const dfp = dfpComPrazo(
    { prazo_execucao_text: '15' },
    [{ id: 'a', label: 'Pintor', quantity: 5, mobilization_days: 10, worked_days: null }],
  );
  const avisos = avisosDePrazo(dfp, 15);
  assert.equal(avisos.length, 1);
  assert.match(avisos[0], /15 dias.*0 dias de execução/);
});

test('aviso de prazo some quando cabeçalho e mão de obra concordam ou não há equipe', () => {
  const coerente = dfpComPrazo(
    { prazo_execucao_text: '30', mobilizacao_text: '5', quantidade_dias_semana: 22, quantidade_sabado: 4, quantidade_domingo: 4 },
    [{ id: 'a', label: 'Pintor', quantity: 2, mobilization_days: 5 }],
  );
  assert.deepEqual(avisosDePrazo(coerente, 30), []);
  // Texto livre de Identificação ("6 meses") não vira prazo em dias: sem cabeçalho, sem aviso.
  assert.deepEqual(avisosDePrazo({ ...coerente, metadata: { ...coerente.metadata, prazo_execucao_text: '6 meses' } }, ''), []);
  const semEquipe = dfpComPrazo({ prazo_execucao_text: '30' }, [{ id: 'a', label: 'Pintor', quantity: 0, mobilization_days: 0 }]);
  assert.deepEqual(avisosDePrazo(semEquipe, 30), []);
  assert.deepEqual(avisosDePrazo({ calculation_version: 1 }), []);
});

test('HH: validação espelha os limites do backend (negativos, horas, hora extra, textos)', () => {
  const hh = modelo();
  const { id: grupoId } = hh.grupos[0];
  const { id: funcaoId } = hh.grupos[0].funcoes[0];
  const casos = [
    [updateHhFuncao(hh, grupoId, funcaoId, 'adicional_noturno_percent', -5), /Adicional noturno/],
    [updateHhFuncao(hh, grupoId, funcaoId, 'horas_mes', 0.5), /horas por mês/],
    [updateHhFuncao(hh, grupoId, funcaoId, 'horas_mes', 800), /horas por mês/],
    [updateHhFuncao(hh, grupoId, funcaoId, 'quantidade', 1e6), /quantidade/],
    [updateHhFuncao(hh, grupoId, funcaoId, 'label', 'x'.repeat(201)), /200 caracteres/],
    [{ ...hh, horas_extras_percentuais: [-10, 80, 100] }, /hora extra 1/],
    [{ ...hh, salario_minimo: -1 }, /salário mínimo/],
  ];
  casos.forEach(([entrada, mensagem]) => assert.match(validateHh(entrada).join(' '), mensagem));
  // Campo apagado ('') vale zero nos dois lados e não bloqueia.
  assert.deepEqual(validateHh({ ...hh, meses: '' }), []);
  assert.equal(computeHhSummary({ ...hh, meses: '' }).totalEstimado, 0);
});
