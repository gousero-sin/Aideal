import { expect, test } from '@playwright/test';

async function setupBudget(page, configure) {
  await page.goto('/?painel=orcamento');
  await page.getByLabel('Usuario').fill('Eduardo');
  await page.getByLabel('Senha').fill('senha-admin-e2e-segura');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Central de Orçamentos' })).toBeVisible();
  const session = await (await page.request.get('/api/auth/session')).json();
  const headers = { 'X-CSRF-Token': session.csrf_token };
  const name = `Regressão ${Date.now()}`;
  const response = await page.request.post('/api/orcamento/orcamentos', {
    headers, data: { contratante: name },
  });
  expect(response.status()).toBe(201);
  const budget = await response.json();
  if (configure) {
    const dfp = configure(budget.revisao_atual.dfp);
    const saved = await page.request.patch(`/api/orcamento/revisoes/${budget.revisao_atual.id}`, {
      headers, data: { dfp },
    });
    expect(saved.status()).toBe(200);
  }
  await page.reload();
  const card = page.locator('.orc-card', { hasText: name });
  await card.getByRole('button', { name: /^Abrir / }).click();
  const editor = page.getByRole('dialog', { name });
  await expect(editor).toBeVisible();
  return { budget, card, editor };
}

test('criação seleciona estado e cidade no campo Região da Obra', async ({ page }) => {
  await page.goto('/?painel=orcamento');
  await page.getByLabel('Usuario').fill('Eduardo');
  await page.getByLabel('Senha').fill('senha-admin-e2e-segura');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  const createForm = page.locator('.orc-create-window form');
  await expect(createForm.getByRole('group', { name: 'Região da Obra' })).toBeVisible();
  await expect(createForm.getByRole('textbox', { name: 'Região da Obra' })).toHaveCount(0);
  await expect(createForm.getByLabel('País', { exact: true })).toHaveValue('Brasil');
  await createForm.getByLabel('Estado', { exact: true }).selectOption('SP');
  await createForm.getByLabel('Cidade', { exact: true }).selectOption('Campinas');
  await expect(createForm.getByLabel('Região selecionada')).toHaveText('Campinas / SP');

  const name = `Criação com região ${Date.now()}`;
  await createForm.getByLabel('Contratante', { exact: true }).fill(name);
  await createForm.getByRole('button', { name: 'Criar orçamento' }).click();
  await expect(page.locator('.orc-card', { hasText: name })).toBeVisible();
  const lista = await (await page.request.get('/api/orcamento/orcamentos')).json();
  const criado = lista.orcamentos.find((item) => item.contratante === name);
  expect(criado.revisao_atual.regiao).toBe('Campinas / SP');
  expect(criado.revisao_atual.dfp.metadata).toMatchObject({ municipio: 'Campinas', uf: 'SP' });
});

test('excluir função com adicional e imposto persiste sem referências inválidas', async ({ page }) => {
  const { budget, editor } = await setupBudget(page, (dfp) => ({
    ...dfp,
    metadata: { ...dfp.metadata, quantidade_dias_semana: 1, horas_semana: 8 },
    mao_de_obra_direta: {
      ...dfp.mao_de_obra_direta,
      items: [{ id: 'pintor', label: 'Pintor regressão', quantity: 1, salary_real: 2200 }],
      adjustments: [{ id: 'periculosidade', label: 'Periculosidade', labor_item_id: 'pintor',
        quantity: 1, percent: 30, base: 'salary' }],
    },
  }));
  await editor.getByRole('button', { name: 'Remover Mão de Obra Direta · Pintor regressão', exact: true }).click();
  const taxRow = editor.locator('.orc-percent-field').filter({ has: page.getByRole('spinbutton', { name: 'Impostos · ISS', exact: true }) });
  await taxRow.getByRole('button', { name: 'Remover', exact: true }).click();
  await editor.getByRole('button', { name: 'Salvar revisão' }).click();
  await expect(editor).toHaveCount(0);
  const saved = await (await page.request.get(`/api/orcamento/orcamentos/${budget.id}`)).json();
  expect(saved.revisao_atual.dfp.mao_de_obra_direta.items).toHaveLength(0);
  expect(saved.revisao_atual.dfp.mao_de_obra_direta.adjustments).toHaveLength(0);
  expect(saved.revisao_atual.dfp.impostos.items.some((item) => item.label === 'ISS')).toBe(false);
});

test('salvar recupera CSRF uma vez e mantém os dados digitados', async ({ page }) => {
  const { budget, editor } = await setupBudget(page);
  let attempts = 0;
  await page.route(`**/api/orcamento/revisoes/${budget.revisao_atual.id}`, async (route) => {
    if (route.request().method() !== 'PATCH') return route.continue();
    attempts += 1;
    if (attempts === 1) return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Token CSRF inválido.' }) });
    return route.continue();
  });
  await editor.getByLabel('Escopo do Serviço').fill('Texto mantido após renovar CSRF');
  await editor.getByRole('button', { name: 'Salvar revisão' }).click();
  await expect(editor).toHaveCount(0);
  expect(attempts).toBe(2);
  const saved = await (await page.request.get(`/api/orcamento/orcamentos/${budget.id}`)).json();
  expect(saved.revisao_atual.escopo).toBe('Texto mantido após renovar CSRF');
});

test('erro de cabeçalho incompleto fica visível dentro do diálogo de situação', async ({ page }) => {
  const { card, editor } = await setupBudget(page);
  await editor.getByRole('button', { name: 'Fechar editor' }).click();
  await card.getByRole('button', { name: 'Em revisão', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Motivo da mudança').fill('Validar cabeçalho incompleto');
  await dialog.getByRole('button', { name: 'Confirmar', exact: true }).click();
  await expect(dialog.getByRole('alert')).toBeVisible();
  await expect(dialog.getByRole('alert')).toContainText(/cabeçalho|obrigatório/i);
  await expect(dialog.getByRole('button', { name: 'Confirmar', exact: true })).toBeEnabled();
});

test('localização mantém a região do cabeçalho sincronizada com cidade e estado', async ({ page }) => {
  const { editor } = await setupBudget(page);
  const header = editor.locator('#orc-section-header');
  await expect(header.getByRole('group', { name: 'Região da Obra' })).toBeVisible();
  await expect(header.getByLabel('País', { exact: true })).toHaveValue('Brasil');
  await expect(header.getByLabel('Estado', { exact: true })).toBeVisible();
  await expect(header.getByLabel('Cidade', { exact: true })).toBeVisible();
  await expect(editor.locator('#orc-section-metadata').getByLabel('Estado', { exact: true })).toHaveCount(0);
  await expect(editor.locator('#orc-section-metadata').getByLabel('Macrorregião', { exact: true })).toHaveCount(0);
  await header.getByLabel('Estado', { exact: true }).selectOption('GO');
  await header.getByLabel('Cidade', { exact: true }).selectOption('Anápolis');
  await expect(header.getByLabel('Região selecionada')).toHaveText('Anápolis / GO');
  await header.getByLabel('Cidade', { exact: true }).selectOption('Goiânia');
  await expect(header.getByLabel('Região selecionada')).toHaveText('Goiânia / GO');
});

test('salário por hora calculado aceita decimais longos sem bloquear o salvamento', async ({ page }) => {
  const { editor } = await setupBudget(page, (dfp) => ({
    ...dfp,
    mao_de_obra_direta: {
      ...dfp.mao_de_obra_direta,
      items: [{
        id: 'pintor-calculado',
        label: 'Pintor calculado',
        quantity: 1,
        salary_real: 3064.64,
      }],
    },
  }));
  const hourlyRate = editor.getByRole('spinbutton', {
    name: 'Mão de Obra Direta · Pintor calculado · Salário/hora',
  });
  await expect(hourlyRate).toHaveAttribute('readonly');
  await expect.poll(() => hourlyRate.evaluate((input) => input.checkValidity())).toBe(true);
  await editor.getByRole('button', { name: 'Salvar revisão' }).click();
  await expect(editor).toHaveCount(0);
});

test('reaproveitar orçamento existente cria o novo sem recusa do código DFP', async ({ page }) => {
  const { budget } = await setupBudget(page, (dfp) => ({
    ...dfp,
    metadata: { ...dfp.metadata, area_total: 2200, quantidade_dias_semana: 20, horas_semana: 8 },
  }));
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Central de Orçamentos' })).toBeVisible();

  await page.getByLabel('Preencher a partir de orçamento existente').selectOption(budget.id);
  const novo = `Reaproveitado ${Date.now()}`;
  await page.getByLabel('Contratante', { exact: true }).fill(novo);
  await page.getByRole('button', { name: 'Criar orçamento' }).click();

  await expect(page.locator('.orc-card', { hasText: novo })).toBeVisible();
  const lista = await (await page.request.get('/api/orcamento/orcamentos')).json();
  const criado = lista.orcamentos.find((item) => item.contratante === novo);
  expect(criado).toBeTruthy();
  // O código DFP é derivado do novo orçamento, não copiado da origem.
  expect(criado.revisao_atual.dfp.metadata.codigo_dfp).toBe(`${criado.codigo}-R0`);
  expect(criado.revisao_atual.dfp.metadata.area_total).toBe(2200);
});

test('barras de rolagem superior e inferior da tabela ficam sincronizadas', async ({ page }) => {
  const { editor } = await setupBudget(page);
  const shell = editor.locator('#orc-section-mao_de_obra_direta .orc-table-shell');
  const bottom = shell.locator('.orc-table-scroll');
  const top = shell.locator('.orc-table-scroll-top');

  // scrollLeft direto em vez de mouse.wheel: o wheel depende da posição do ponteiro
  // e tornava o teste intermitente.
  await bottom.evaluate((el) => { el.scrollLeft = 420; });
  await expect.poll(() => top.evaluate((el) => el.scrollLeft)).toBe(420);

  await top.evaluate((el) => { el.scrollLeft = 300; });
  await expect.poll(() => bottom.evaluate((el) => el.scrollLeft)).toBe(300);

  // O título da coluna congelada acompanha a rolagem horizontal junto com ela.
  const alinhados = await shell.evaluate((el) => {
    const cabecalho = el.querySelector('thead th').getBoundingClientRect().left;
    const coluna = el.querySelector('tbody th').getBoundingClientRect().left;
    return Math.abs(cabecalho - coluna) < 1;
  });
  expect(alinhados).toBe(true);
});

test('campo de dias mostra o valor herdado e jornada zerada não zera a mão de obra', async ({ page }) => {
  const { editor } = await setupBudget(page, (dfp) => ({
    ...dfp,
    metadata: { ...dfp.metadata, quantidade_dias_semana: 20, horas_semana: 0 },
    mao_de_obra_direta: {
      ...dfp.mao_de_obra_direta,
      items: [{ id: 'pintor', label: 'Pintor', quantity: 4, salary_real: 2200 }],
      adjustments: [],
    },
  }));

  // Em branco, o campo de dias anuncia de onde vem o valor em vez de ficar mudo.
  const dias = editor.getByRole('spinbutton', { name: 'Mão de Obra Direta · Pintor · Qtd. dias' });
  await expect(dias).toHaveValue('');
  await expect(dias).toHaveAttribute('placeholder', '20');

  // Desde a regra 220/30 cada diária vale 220/30 h: a jornada diária não entra no cálculo,
  // some da tela e, zerada, não gera aviso (4 pessoas × 20 dias × 220/30 = 586,67 h).
  await expect(editor.getByRole('spinbutton', { name: 'Mão de Obra Direta · Pintor · Horas trabalhadas (equipe)' }))
    .toHaveValue('586.67');
  await expect(editor.getByRole('spinbutton', { name: /^Horas (por dia de )?semana$/ })).toHaveCount(0);
  await expect(editor.locator('.orc-summary-warnings', { hasText: /jornada/i })).toHaveCount(0);
});
