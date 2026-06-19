import test from 'node:test';
import assert from 'node:assert/strict';

import { buildDREPanelQuery } from './financialPanelUtils.js';

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
