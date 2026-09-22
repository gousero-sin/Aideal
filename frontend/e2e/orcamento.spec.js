import { expect, test } from '@playwright/test';

const ADMIN_PASSWORD = 'senha-admin-e2e-segura';

async function loginAsOwner(page) {
  await page.goto('/');
  await page.getByLabel('Usuario').fill('Eduardo');
  await page.getByLabel('Senha').fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.locator('.access-sidebar')).toBeVisible();
  await page.getByRole('button', { name: 'Orçamento', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Central de Orçamentos' })).toBeVisible();
}

test('cria, abre por clique e persiste um snapshot DFP completo em goflow-window', async ({ page }) => {
  const contratante = `Contratante DFP E2E ${Date.now()}`;
  await loginAsOwner(page);

  const createWindow = page.locator('.orc-create-window');
  await expect(createWindow.getByLabel('Modalidade do Trabalho').locator('option')).toHaveText([
    'Selecione', 'HH', 'Spot', 'Rotina', 'm²',
  ]);
  await createWindow.getByLabel('Contratante', { exact: true }).fill(contratante);
  await createWindow.getByRole('button', { name: 'Criar orçamento' }).click();

  const card = page.locator('.orc-card', { hasText: contratante });
  await expect(card).toBeVisible();
  await expect(card).not.toHaveAttribute('role', 'button');
  await card.getByRole('button', { name: new RegExp(`Abrir .*${contratante}`) }).click();

  const editor = page.getByRole('dialog', { name: contratante });
  await expect(editor).toBeVisible();
  expect(await editor.locator('.goflow-window').count()).toBeGreaterThan(10);

  await editor.getByLabel('Dados da Contratante').fill('Cadastro completo AMBEV');
  await editor.getByLabel('Escopo do Serviço').fill('Hidrojateamento e pintura');
  await editor.getByLabel('Modalidade do Trabalho').selectOption('Spot');
  await editor.getByLabel('Prazo de execução (dias)').fill('10');
  await expect(editor.getByLabel('Saldo de Mão de Obra')).toHaveCount(0);
  await expect(editor.getByLabel('Forma de tributação')).toHaveCount(0);
  await expect(editor.getByLabel('Código DFP')).toHaveCount(0);
  await expect(editor.getByRole('columnheader', { name: 'Horas / empregado' })).toHaveCount(0);
  await expect(editor.getByRole('columnheader', { name: 'Horas base' })).toHaveCount(0);
  await expect(editor.getByRole('columnheader', { name: 'Horas extras semanais' })).toBeVisible();
  await expect(editor.getByRole('columnheader', { name: 'Horas extras sábado' })).toBeVisible();
  await expect(editor.getByRole('columnheader', { name: 'Horas extras domingo' })).toBeVisible();
  await expect(editor.getByLabel(/Mão de Obra Direta · .* · Quantidade de pessoas/).first()).toHaveAttribute('step', '1');
  await expect(editor.getByRole('columnheader', { name: 'Qtd. média' })).toHaveCount(0);
  await expect(editor.getByLabel(/Mão de Obra Direta · .* · Salário\/hora/).first()).toHaveAttribute('readonly', '');
  await editor.getByRole('checkbox', { name: 'N/A — início não definido' }).check();
  await editor.getByLabel('Área total').fill('858');
  await expect(editor.getByLabel('País')).toHaveValue('Brasil');
  await editor.getByLabel('Estado').selectOption('GO');
  await expect(editor.getByLabel('Cidade').locator('option')).toContainText(['Anápolis']);
  await editor.getByLabel('Cidade').selectOption('Anápolis');
  await expect(editor.getByLabel('Região selecionada')).toHaveText('Anápolis / GO');
  await expect(editor.getByLabel('Macrorregião')).toHaveCount(0);

  const laborScroll = editor.getByRole('region', { name: 'Mão de Obra Direta, tabela rolável' });
  const scrollMetrics = await laborScroll.evaluate((element) => ({
    clientWidth: element.clientWidth,
    overflowX: getComputedStyle(element).overflowX,
    scrollWidth: element.scrollWidth,
  }));
  expect(scrollMetrics.overflowX).toBe('auto');
  expect(scrollMetrics.scrollWidth).toBeGreaterThan(scrollMetrics.clientWidth);
  await expect(editor.locator('.orc-table-scroll-top').first()).toBeVisible();

  await editor.getByLabel('Equipamentos · COMPRESSOR ELÉTRICO · Quantidade').fill('2');
  await editor.getByLabel('Equipamentos · COMPRESSOR ELÉTRICO · Custo unitário').fill('1500');
  await editor.getByLabel('Custos indiretos · ADM CENTRAL').fill('5');
  await editor.getByLabel('Impostos · ISS').fill('5');
  await editor.getByLabel('Fator BDI (%)').fill('20');

  const patchRequestPromise = page.waitForRequest((request) => (
    request.method() === 'PATCH' && /\/api\/orcamento\/revisoes\/[^/]+$/.test(request.url())
  ));
  await editor.getByRole('button', { name: 'Salvar revisão' }).click();
  const patchRequest = await patchRequestPromise;
  expect(patchRequest.headers()['x-csrf-token']).toBeTruthy();
  expect(patchRequest.postDataJSON().dfp.metadata).toMatchObject({
    area_total: 858,
    data_inicio: null,
    data_inicio_na: true,
    macrorregiao: 'Centro-Oeste',
    municipio: 'Anápolis',
    uf: 'GO',
  });

  await expect(editor).toHaveCount(0);
  await expect(card).not.toContainText('Cabeçalho pendente');
  await card.getByRole('button', { name: new RegExp(`Abrir .*${contratante}`) }).click();
  const reopened = page.getByRole('dialog', { name: contratante });
  await expect(reopened.getByLabel('Código DFP')).toHaveCount(0);
  await expect(reopened.getByRole('checkbox', { name: 'N/A — início não definido' })).toBeChecked();
  await expect(reopened.getByLabel('Equipamentos · COMPRESSOR ELÉTRICO · Custo unitário')).toHaveValue('1500');

  await reopened.getByRole('button', { name: 'Minimizar editor' }).click();
  await expect(reopened.locator('.orc-editor-layout')).toHaveCount(0);
  await reopened.getByRole('button', { name: 'Restaurar editor' }).click();
  await reopened.getByRole('button', { name: 'Fechar editor' }).click();
  await expect(reopened).toHaveCount(0);
});

test('carteira e editor são responsivos em viewport móvel', async ({ page }) => {
  await loginAsOwner(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('.orc-root')).toBeVisible();
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll');

  const firstCard = page.locator('.orc-card').first();
  if (await firstCard.count()) {
    await firstCard.getByRole('button', { name: /^Abrir / }).click();
    const editor = page.locator('.orc-editor-dialog');
    await expect(editor).toBeVisible();
    await expect(editor).toHaveCSS('width', '390px');
  }
});
