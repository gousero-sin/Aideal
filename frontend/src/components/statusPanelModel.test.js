import test from 'node:test';
import assert from 'node:assert/strict';

import { resolveProcessamentoTotal } from './statusPanelModel.js';

test('usa total_lancamentos quando metadata não informa bd_fluxo_registros_reais', () => {
  assert.equal(
    resolveProcessamentoTotal({
      total_lancamentos: 926,
      total_registros: 0,
      registros_processados: 0,
    }),
    926,
  );
});

test('prioriza bd_fluxo_registros_reais quando presente no metadata', () => {
  assert.equal(
    resolveProcessamentoTotal({
      total_lancamentos: 926,
      metadata: {
        bd_fluxo_registros_reais: 913,
      },
    }),
    913,
  );
});

test('ignora metadata zerado quando há total_lancamentos positivo', () => {
  assert.equal(
    resolveProcessamentoTotal({
      total_lancamentos: 926,
      metadata: {
        bd_fluxo_registros_reais: 0,
      },
    }),
    926,
  );
});

test('retorna zero quando não há total disponível', () => {
  assert.equal(resolveProcessamentoTotal(null), 0);
});
