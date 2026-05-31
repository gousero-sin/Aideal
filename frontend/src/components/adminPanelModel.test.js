import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildProcessNotification,
  buildValidationNotification,
  createInitialAdminState,
  updateAdminFlowState,
} from './adminPanelModel.js';

test('atualiza estado do fluxo admin sem mutar o estado anterior', () => {
  const initial = createInitialAdminState();
  const validacao = { valido: true };
  const updated = updateAdminFlowState(initial, 'dre', { validacao });

  assert.equal(initial.dre.validacao, null);
  assert.deepEqual(updated.dre.validacao, validacao);
  assert.notEqual(updated, initial);
  assert.notEqual(updated.dre, initial.dre);
  assert.equal(updated.fluxo_caixa, initial.fluxo_caixa);
});

test('gera notificacao de validacao por fluxo', () => {
  assert.deepEqual(
    buildValidationNotification('dre', { valido: true }),
    { type: 'success', message: 'Estrutura DRE validada com sucesso.' },
  );
  assert.deepEqual(
    buildValidationNotification('fluxo_caixa', { valido: false, erros: [{ campo: 'x' }] }),
    { type: 'error', message: 'Validação Fluxo com 1 erro(s).' },
  );
});

test('gera notificacao de processo para ingestao limpeza erro e geracao', () => {
  assert.deepEqual(
    buildProcessNotification('dre', { _stage: 'ingestao', total_lancamentos: 12 }),
    { type: 'success', message: 'Mês DRE salvo no banco com 12 lançamento(s).' },
  );
  assert.deepEqual(
    buildProcessNotification('fluxo_caixa', { _stage: 'limpeza', _competenciaLabel: '05/2025' }),
    { type: 'success', message: 'Mês Fluxo de Caixa 05/2025 excluído e painel atualizado.' },
  );
  assert.deepEqual(
    buildProcessNotification('dre', { _stage: 'geracao', erros: [{ campo: 'arquivo' }] }),
    { type: 'error', message: 'DRE com 1 erro(s) na etapa geracao.' },
  );
  assert.deepEqual(
    buildProcessNotification('fluxo_caixa', { total_lancamentos: 3 }),
    { type: 'success', message: 'Fluxo de Caixa gerado com 3 movimento(s).' },
  );
});
