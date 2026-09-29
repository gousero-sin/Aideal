import { expect, request, test } from '@playwright/test';

const ADMIN_PASSWORD = 'senha-admin-e2e-segura';

async function login(page, username, password, { expectSidebar = true, view = null } = {}) {
  const target = view ? `/?painel=${view}` : '/';
  await page.goto(target);
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: 'Entrar' }).click();
  if (expectSidebar) await expect(page.locator('.access-sidebar')).toBeVisible();
}

test('Eduardo controla acessos e a revogacao tem efeito imediato', async ({ page }) => {
  const suffix = `${Date.now()}`;
  const username = `ana.e2e.${suffix}`;
  const senhaTemporaria = 'senha-temporaria-e2e-123';
  const drePainelStub = JSON.stringify({
    periodo: { ano: 2025 },
    filtros_aplicados: {},
    filtros_disponiveis: {
      meses: [],
      centro_custo: [],
      natureza: [],
    },
    kpis: {},
    series_mensais: [],
    ranking_obras: [],
    indicadores_viabilidade: [],
    objetivos_estrategicos: [],
  });

  await login(page, 'Eduardo', ADMIN_PASSWORD, { view: 'usuarios' });
  await expect(page.locator('.access-sidebar-item')).toHaveCount(5);
  await page.getByRole('button', { name: 'Controle de Acessos' }).click();

  const createForm = page.locator('.access-create-card');
  await createForm.getByLabel('Nome de usuario').fill(username);
  await createForm.getByLabel('Nome de exibicao').fill('Ana E2E');
  await createForm.getByLabel('Senha inicial').fill(senhaTemporaria);
  await createForm.getByLabel('Visualizar Painel DRE').check();
  await createForm.getByRole('button', { name: 'Criar usuario' }).click();
  await expect(page.getByText(`@${username}`)).toBeVisible();

  const usersResponse = await page.request.get('/api/admin/users');
  expect(usersResponse.status()).toBe(200);
  const createdUser = (await usersResponse.json()).users.find(
    (candidate) => candidate.username === username,
  );
  expect(createdUser).toBeTruthy();

  await page.getByRole('button', { name: 'Sair' }).click();
  // Este cenário valida acesso e revogação; o painel DRE em si já tem cobertura própria.
  await page.route('**/api/dre/painel**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: drePainelStub,
    });
  });
  await login(page, username, senhaTemporaria, { expectSidebar: false });
  await expect(page.getByRole('heading', { name: 'Crie sua senha definitiva' })).toBeVisible();
  await page.getByLabel('Senha atual (temporaria)').fill(senhaTemporaria);
  await page.getByLabel('Nova senha', { exact: true }).fill('senha-definitiva-e2e-123');
  await page.getByLabel('Confirme a nova senha').fill('senha-definitiva-e2e-123');
  await page.getByRole('button', { name: 'Definir nova senha' }).click();
  await expect(page.locator('.access-sidebar')).toBeVisible();
  await expect(page.locator('.access-sidebar-item')).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'DRE', exact: true })).toBeVisible();
  const sessionResponse = await page.request.get('/api/auth/session');
  expect(sessionResponse.status()).toBe(200);
  const sessionPayload = await sessionResponse.json();
  expect(sessionPayload.authenticated).toBe(true);
  expect(sessionPayload.modules).toEqual([
    { id: 'dre', label: 'DRE', permission: 'dre.view' },
  ]);
  expect((await page.request.get('/api/fluxo_caixa/painel?ano=2025')).status()).toBe(403);
  expect((await page.request.get('/api/admin/users')).status()).toBe(403);

  const adminApi = await request.newContext({ baseURL: 'http://127.0.0.1:8011' });
  await adminApi.post('/api/auth/login', {
    data: { username: 'Eduardo', password: ADMIN_PASSWORD },
  });
  const adminSession = await adminApi.get('/api/auth/session');
  const { csrf_token: csrfToken } = await adminSession.json();
  const deactivated = await adminApi.patch(`/api/admin/users/${createdUser.id}`, {
    data: { active: false },
    headers: { 'X-CSRF-Token': csrfToken },
  });
  expect(deactivated.status()).toBe(200);
  await adminApi.dispose();

  expect((await page.request.get('/api/auth/session')).status()).toBe(401);
  expect((await page.request.get('/api/dre/painel?ano=2025')).status()).toBe(401);
});

test('administrador redefine senha temporaria e exclui usuario com confirmacao', async ({ page }) => {
  const username = `reset.e2e.${Date.now()}`;
  const novaSenha = 'nova-temporaria-e2e-123';

  await login(page, 'Eduardo', ADMIN_PASSWORD, { view: 'usuarios' });
  await page.getByRole('button', { name: 'Controle de Acessos' }).click();
  const ownerCard = page.locator('.access-user-card', { hasText: '@Eduardo' });
  await expect(ownerCard.getByRole('button', { name: 'Redefinir senha' })).toHaveCount(0);
  await expect(ownerCard.getByRole('button', { name: 'Excluir usuario' })).toHaveCount(0);

  const createForm = page.locator('.access-create-card');
  await createForm.getByLabel('Nome de usuario').fill(username);
  await createForm.getByLabel('Nome de exibicao').fill('Reset E2E');
  await createForm.getByLabel('Senha inicial').fill('senha-inicial-e2e-123');
  await createForm.getByLabel('Visualizar Painel DRE').check();
  await createForm.getByRole('button', { name: 'Criar usuario' }).click();
  const userCard = page.locator('.access-user-card', { hasText: `@${username}` });
  await expect(userCard).toBeVisible();

  await userCard.getByRole('button', { name: 'Redefinir senha' }).click();
  await userCard.getByLabel('Nova senha temporaria para Reset E2E').fill('curta');
  await userCard.getByRole('button', { name: 'Confirmar nova senha' }).click();
  await expect(userCard.getByText('A senha temporaria deve ter pelo menos 10 caracteres.')).toBeVisible();
  await userCard.getByLabel('Nova senha temporaria para Reset E2E').fill(novaSenha);
  const resetResponse = page.waitForResponse((response) => (
    response.request().method() === 'PATCH' && response.url().includes('/api/admin/users/')
  ));
  await userCard.getByRole('button', { name: 'Confirmar nova senha' }).click();
  expect((await resetResponse).status()).toBe(200);
  await expect(userCard.getByLabel('Nova senha temporaria para Reset E2E')).toHaveCount(0);

  await page.getByRole('button', { name: 'Sair' }).click();
  await login(page, username, novaSenha, { expectSidebar: false });
  await expect(page.getByRole('heading', { name: 'Crie sua senha definitiva' })).toBeVisible();
  await page.getByLabel('Senha atual (temporaria)').fill(novaSenha);
  await page.getByLabel('Nova senha', { exact: true }).fill('senha-final-e2e-123');
  await page.getByLabel('Confirme a nova senha').fill('senha-final-e2e-123');
  await page.getByRole('button', { name: 'Definir nova senha' }).click();
  await expect(page.locator('.access-sidebar')).toBeVisible();
  await page.getByRole('button', { name: 'Sair' }).click();

  await login(page, 'Eduardo', ADMIN_PASSWORD, { view: 'usuarios' });
  await page.getByRole('button', { name: 'Controle de Acessos' }).click();
  const cardToDelete = page.locator('.access-user-card', { hasText: `@${username}` });
  await cardToDelete.getByRole('button', { name: 'Excluir usuario' }).click();
  await cardToDelete.getByRole('button', { name: 'Cancelar' }).click();
  await expect(cardToDelete).toBeVisible();
  await cardToDelete.getByRole('button', { name: 'Excluir usuario' }).click();
  const deleteResponse = page.waitForResponse((response) => (
    response.request().method() === 'DELETE' && response.url().includes('/api/admin/users/')
  ));
  await cardToDelete.getByRole('button', { name: 'Confirmar exclusao' }).click();
  expect((await deleteResponse).status()).toBe(204);
  await expect(cardToDelete).toHaveCount(0);
});

test('Orcamento so aparece para quem tem orcamento.view e preserva revisoes', async ({ page }) => {
  const suffix = `${Date.now()}`;
  const username = `bruno.e2e.${suffix}`;
  const temporaria = 'senha-temporaria-e2e-123';
  const definitiva = 'senha-definitiva-e2e-123';
  const contratante = `AMBEV E2E ${suffix}`;

  test.setTimeout(60_000);
  await login(page, 'Eduardo', ADMIN_PASSWORD, { view: 'usuarios' });
  await page.getByRole('button', { name: 'Controle de Acessos' }).click();

  const createForm = page.locator('.access-create-card');
  await createForm.getByLabel('Nome de usuario').fill(username);
  await createForm.getByLabel('Nome de exibicao').fill('Bruno E2E');
  await createForm.getByLabel('Senha inicial').fill(temporaria);
  await createForm.getByLabel('Visualizar Orcamento').check();
  await createForm.getByLabel('Criar e editar Orcamento').check();
  await createForm.getByLabel('Alterar situacao do Orcamento').check();
  const createUserResponse = page.waitForResponse((response) => (
    response.request().method() === 'POST'
      && response.url().endsWith('/api/admin/users')
  ));
  await createForm.getByRole('button', { name: 'Criar usuario' }).click();
  expect((await createUserResponse).status()).toBe(201);

  const usersResponse = await page.request.get('/api/admin/users');
  expect(usersResponse.status()).toBe(200);
  const createdUser = (await usersResponse.json()).users.find(
    (candidate) => candidate.username === username,
  );
  expect(createdUser).toBeTruthy();

  await page.getByRole('button', { name: 'Sair' }).click();
  await login(page, username, temporaria, { expectSidebar: false, view: 'orcamento' });
  await page.getByLabel('Senha atual (temporaria)').fill(temporaria);
  await page.getByLabel('Nova senha', { exact: true }).fill(definitiva);
  await page.getByLabel('Confirme a nova senha').fill(definitiva);
  await page.getByRole('button', { name: 'Definir nova senha' }).click();
  await expect(page.locator('.access-sidebar')).toBeVisible();

  // Menu mostra apenas o modulo concedido; o backend recusa os demais.
  await expect(page.locator('.access-sidebar-item')).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Orçamento', exact: true })).toBeVisible();
  expect((await page.request.get('/api/dre/painel?ano=2025')).status()).toBe(403);
  expect((await page.request.get('/api/admin/users')).status()).toBe(403);
  expect((await page.request.get('/api/orcamento/orcamentos')).status()).toBe(200);

  const novo = page.locator('.orc-create-window');
  await novo.getByLabel('Contratante', { exact: true }).fill(contratante);
  await novo.getByLabel('Dados da Contratante').fill('AMBEV S.A. — Anápolis');
  await novo.getByLabel('Escopo do Serviço').fill('Hidrojateamento e pintura');
  await novo.getByLabel('Modalidade do Trabalho').selectOption('Spot');
  await novo.getByLabel('Prazo de execução (dias)').fill('10');
  await expect(novo.getByLabel('Saldo de Mão de Obra')).toHaveCount(0);
  const location = novo.getByRole('group', { name: 'Região da Obra' });
  await location.getByRole('combobox', { name: 'Estado' }).selectOption('GO');
  await location.getByRole('combobox', { name: 'Cidade' }).selectOption('Anápolis');
  await novo.getByRole('button', { name: 'Criar orçamento' }).click();

  // O código é sequencial e a base pode já conter dados de outros testes.
  const card = page.locator('.orc-card', { hasText: contratante });
  await expect(card).toBeVisible();
  await expect(card.locator('.goflow-window__eyebrow')).toHaveText(/^ORC-\d{4,}-R0$/);
  await expect(card.locator('.orc-badge')).toHaveText('Rascunho');
  await expect(card.locator('.orc-revision-chip')).toHaveCount(1);

  // Rascunho nao oferece salto direto para "Pronto para proposta".
  await expect(card.getByRole('button', { name: 'Pronto para proposta' })).toHaveCount(0);

  const changeSituation = async (label, reason) => {
    await card.getByRole('button', { name: label, exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Motivo da mudança').fill(reason);
    await dialog.getByRole('button', { name: 'Confirmar' }).click();
    await expect(dialog).toHaveCount(0);
  };
  await changeSituation('Em revisão', 'início da revisão');
  await expect(card.locator('.orc-badge')).toHaveText('Em revisão');

  await changeSituation('Pronto para proposta', 'custos conferidos');
  await expect(card.locator('.orc-badge')).toHaveText('Pronto para proposta');

  await changeSituation('Emitido', 'emissão ao cliente');
  await expect(card.locator('.orc-badge')).toHaveText('Emitido');
  await expect(card.locator('.orc-card-meta > div').filter({ hasText: 'Validade' }).locator('dd')).toHaveText(/\d{2}\/\d{2}\/\d{4}/);

  // Nova revisão herda o cabeçalho inteiro e preserva a anterior na trilha.
  await card.getByRole('button', { name: 'Nova revisão' }).click();
  await expect(card.locator('.orc-revision-chip')).toHaveCount(2);
  await expect(card.locator('.orc-badge')).toHaveText('Rascunho');
  // O cabeçalho veio junto, então a revisão nova não reabre pendências.
  await expect(card).not.toContainText('Cabeçalho pendente');
});
