import test from 'node:test';
import assert from 'node:assert/strict';

import { buildDREExportRequest, buildDREPanelQuery } from './financialPanelUtils.js';

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
