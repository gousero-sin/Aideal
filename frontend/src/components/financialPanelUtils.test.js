import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildDREExportRequest,
  buildDREPanelQuery,
  buildResultadoLiquidoKpi,
} from './financialPanelUtils.js';

test('monta query do DRE respeitando mes quando obra e centro de custos estao filtrados', () => {
  const query = buildDREPanelQuery({
    ano: 2026,
    meses: [5],
    centro_custo: ['Obra Alpha'],
    natureza: ['Custos Fixos'],
  });

  const params = new URLSearchParams(query);

  assert.equal(params.get('ano'), '2026');
  assert.deepEqual(params.getAll('meses'), ['5']);
  assert.deepEqual(params.getAll('centro_custo'), ['Obra Alpha']);
  assert.deepEqual(params.getAll('natureza'), ['Custos Fixos']);
  assert.equal(params.has('escopo_periodo'), false);
});

test('monta exportação do DRE para exatamente uma obra e os meses selecionados', () => {
  assert.deepEqual(buildDREExportRequest({
    ano: '2026',
    meses: [2, 5],
    centro_custo: ['Obra Alpha'],
  }, {
    periodo: { ano: 2026 },
    filtros_disponiveis: { meses: [1, 2, 3, 4, 5] },
  }), {
    valid: true,
    centroCusto: 'Obra Alpha',
    competencia: '05/2026',
    meses: [2, 5],
  });
});

test('exportação do DRE usa o último mês disponível quando nenhum mês foi marcado', () => {
  assert.deepEqual(buildDREExportRequest({
    ano: '',
    meses: [],
    centro_custo: ['Obra Beta'],
  }, {
    periodo: { ano: 2025 },
    filtros_disponiveis: { meses: [1, 3, 8] },
  }), {
    valid: true,
    centroCusto: 'Obra Beta',
    competencia: '08/2025',
    meses: [1, 3, 8],
  });
});

test('exportação do DRE exige uma única obra', () => {
  assert.equal(buildDREExportRequest({ centro_custo: [] }, {}).valid, false);
  assert.equal(buildDREExportRequest({ centro_custo: ['A', 'B'] }, {}).valid, false);
});

test('card de resultado usa o Resultado Líquido do DRE e detalha antes do IR e gerencial', () => {
  const kpi = buildResultadoLiquidoKpi({
    saldo_liquido: -252927.13,
    resultado_antes_ir: 162349.01,
    resultado_liquido: -56845.76,
    resultado_gerencial: -149405.96,
  });

  assert.equal(kpi.value, -56845.76);
  assert.match(kpi.detail, /^antes do IR \+R\$\s162\.349 · gerencial -R\$\s149\.406$/);
});

test('card de resultado cai para o saldo quando a API não envia o Resultado Líquido', () => {
  const kpi = buildResultadoLiquidoKpi({ saldo_liquido: 1200 });

  assert.equal(kpi.value, 1200);
  assert.equal(kpi.detail, 'resultado líquido do DRE');
});
