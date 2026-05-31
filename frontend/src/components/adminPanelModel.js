import { formatNumber } from './financialPanelUtils.js';
import { resolveProcessamentoTotal } from './statusPanelModel.js';

export const ADMIN_FLOWS = {
  dre: {
    label: 'DRE',
    ingestaoSuccess: (total) => `Mês DRE salvo no banco com ${formatNumber(total)} lançamento(s).`,
    limpezaSuccess: (competencia) => `Mês DRE ${competencia || ''} excluído e painel atualizado.`,
    geracaoSuccess: (total) => `DRE final gerado com ${formatNumber(total)} lançamento(s).`,
    validacaoSuccess: 'Estrutura DRE validada com sucesso.',
    validacaoError: (count) => `Validação DRE com ${formatNumber(count)} erro(s).`,
    processError: (count, stage) => `DRE com ${formatNumber(count)} erro(s) na etapa ${stage || 'operacional'}.`,
  },
  fluxo_caixa: {
    label: 'Fluxo de Caixa',
    ingestaoSuccess: (total) => `Lote Fluxo salvo no banco com ${formatNumber(total)} movimento(s).`,
    limpezaSuccess: (competencia) =>
      `Mês Fluxo de Caixa ${competencia || ''} excluído e painel atualizado.`,
    geracaoSuccess: (total) => `Fluxo de Caixa gerado com ${formatNumber(total)} movimento(s).`,
    validacaoSuccess: 'Estrutura do Fluxo de Caixa validada com sucesso.',
    validacaoError: (count) => `Validação Fluxo com ${formatNumber(count)} erro(s).`,
    processError: (count, stage) =>
      `Fluxo de Caixa com ${formatNumber(count)} erro(s) na etapa ${stage || 'operacional'}.`,
  },
};

export const createEmptyAdminFlowState = () => ({
  validacao: null,
  processamento: null,
});

export const createInitialAdminState = () => ({
  dre: createEmptyAdminFlowState(),
  fluxo_caixa: createEmptyAdminFlowState(),
});

export const updateAdminFlowState = (state, fluxo, patch) => ({
  ...state,
  [fluxo]: {
    ...(state[fluxo] || createEmptyAdminFlowState()),
    ...patch,
  },
});

export const buildValidationNotification = (fluxo, result) => {
  if (!result) return null;
  const model = ADMIN_FLOWS[fluxo] || ADMIN_FLOWS.dre;
  const count = result.erros?.length || 0;
  return result.valido
    ? { type: 'success', message: model.validacaoSuccess }
    : { type: 'error', message: model.validacaoError(count) };
};

export const buildProcessNotification = (fluxo, result) => {
  if (!result) return null;
  const model = ADMIN_FLOWS[fluxo] || ADMIN_FLOWS.dre;
  const temErro = result?.erros?.length > 0 || result?.status === 'error' || result?.sucesso === false;
  const count = result?.erros?.length || 0;

  if (temErro) {
    return { type: 'error', message: model.processError(count, result?._stage) };
  }

  const total = resolveProcessamentoTotal(result);
  if (result?._stage === 'ingestao') {
    return { type: 'success', message: model.ingestaoSuccess(total) };
  }
  if (result?._stage === 'limpeza') {
    return { type: 'success', message: model.limpezaSuccess(result?._competenciaLabel) };
  }
  return { type: 'success', message: model.geracaoSuccess(total) };
};
