export function resolveProcessamentoTotal(processamento) {
  const processamentoMeta = processamento?.metadata || {};
  const totalMeta = processamentoMeta?.bd_fluxo_registros_reais;
  const totalLancamentos = processamento?.registros_reais ?? processamento?.total_lancamentos;

  if (typeof totalMeta === 'number' && totalMeta > 0) {
    return totalMeta;
  }

  if (typeof totalLancamentos === 'number' && totalLancamentos > 0) {
    return totalLancamentos;
  }

  return totalMeta ?? totalLancamentos ?? processamento?.registros_processados ?? processamento?.total_registros ?? processamento?.inseridos ?? 0;
}
