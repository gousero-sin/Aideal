import { expect, test } from '@playwright/test';

const panelPayload = {
  success: true,
  periodo: { ano: 2026, label: '2026' },
  filtros_disponiveis: {
    anos: [2026],
    meses: [1, 2, 5],
    centro_custo: [
      { value: 'Obra Alpha', label: 'Obra Alpha', total: 12 },
      { value: 'Obra Beta', label: 'Obra Beta', total: 8 },
    ],
    natureza: [],
  },
  filtros_aplicados: { ano: 2026, meses: [], centro_custo: [], natureza: [] },
  kpis: {},
  indicadores_viabilidade: [],
  objetivos_estrategicos: [],
  series_mensais: [],
  ranking_obras: [],
  ranking_naturezas: [],
  ultimos_lancamentos: [],
};

test('exporta o DRE somente da obra selecionada no painel', async ({ page }) => {
  await page.route('**/api/dre/painel*', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(panelPayload),
  }));

  let exportBody = '';
  await page.route('**/api/dre/exportar', async (route) => {
    exportBody = route.request().postData() || '';
    await route.fulfill({
      status: 200,
      contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      headers: { 'Content-Disposition': 'attachment; filename="DRE_Obra_Alpha.xlsx"' },
      body: 'xlsx filtrado',
    });
  });

  await page.goto('/?painel=dre');
  await page.getByLabel('Usuario').fill('Eduardo');
  await page.getByLabel('Senha').fill('senha-admin-e2e-segura');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Resultado por obra e centro de custos' })).toBeVisible();

  const exportButton = page.getByRole('button', { name: 'Exportar DRE da obra' });
  await expect(exportButton).toBeDisabled();
  await page.getByRole('button', { name: /Obra Alpha/ }).click();
  await expect(exportButton).toBeEnabled();

  const downloadPromise = page.waitForEvent('download');
  await exportButton.click();
  const download = await downloadPromise;

  expect(download.suggestedFilename()).toBe('DRE_Obra_Alpha.xlsx');
  expect(exportBody).toContain('Obra Alpha');
  expect(exportBody).toContain('05/2026');
  expect(exportBody).not.toContain('Obra Beta');
  await expect(page.getByText('DRE da obra Obra Alpha exportado.')).toBeVisible();
});
