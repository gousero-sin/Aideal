import { expect, test } from '@playwright/test';

const loaderFor = (page) => page.getByRole('status', { name: 'Carregando Orçamento' });
const ready = (page) => expect(page.getByRole('heading', { name: 'Central de Orçamentos' })).toBeVisible();

async function login(page) {
  await page.goto('/?painel=orcamento');
  await page.getByLabel('Usuario').fill('Eduardo');
  await page.getByLabel('Senha').fill('senha-admin-e2e-segura');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
}

function gate() {
  let release;
  const promise = new Promise((resolve) => { release = resolve; });
  return { promise, release };
}

async function delayInitial(page) {
  const pending = gate();
  await page.route('**/api/orcamento/{orcamentos,schema}', async (route) => {
    await pending.promise;
    await route.continue();
  });
  return pending;
}

async function createAndOpen(page) {
  const name = `UI motion ${Date.now()}`;
  await page.locator('.orc-create-window').getByLabel('Contratante', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Criar orçamento', exact: true }).click();
  const opener = page.locator('.orc-card', { hasText: name }).getByRole('button', { name: /^Abrir / });
  await opener.click();
  const editor = page.getByRole('dialog', { name });
  await expect(editor).toBeVisible();
  return { editor, opener };
}

test('loader permanece durante requests iniciais e revela a carteira ao concluir', async ({ page }) => {
  const pending = await delayInitial(page);
  await login(page);
  const loader = loaderFor(page);
  await expect(loader).toBeVisible();
  await expect(loader.getByText('goflowOS', { exact: true })).toBeVisible();
  await expect(loader.getByText('Orçamento', { exact: true })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Paineis liberados' })).toBeVisible();
  await expect(page.locator('.orc-create-window')).toHaveCount(0);
  pending.release();
  await ready(page);
  await expect(loader).toHaveCount(0);
});

test('carregamento rápido conclui sem manter loader artificialmente', async ({ page }) => {
  await login(page);
  await ready(page);
  await expect(loaderFor(page)).toHaveCount(0);
});

test('erro inicial permite tentar novamente', async ({ page }) => {
  await page.route('**/api/orcamento/schema', (route) => route.fulfill({
    status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Catálogo indisponível' }),
  }));
  await login(page);
  await expect(page.getByRole('button', { name: 'Tentar novamente' })).toBeVisible();
  await expect(loaderFor(page)).toHaveCount(0);
  await page.unroute('**/api/orcamento/schema');
  await page.getByRole('button', { name: 'Tentar novamente' }).click();
  await ready(page);
});

test('sair durante carregamento e reentrar reinicia a tela inicial', async ({ page }) => {
  const pending = await delayInitial(page);
  await login(page);
  await expect(loaderFor(page)).toBeVisible();
  const otherModule = page.locator('.access-sidebar-item').filter({ hasNotText: 'Orçamento' }).first();
  await otherModule.click();
  await expect(loaderFor(page)).toHaveCount(0);
  await page.getByRole('button', { name: 'Orçamento', exact: true }).click();
  await expect(loaderFor(page)).toBeVisible();
  pending.release();
  await ready(page);
});

test('movimento reduzido mantém o símbolo estático', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const pending = await delayInitial(page);
  await login(page);
  const loader = loaderFor(page);
  await expect(loader).toHaveAttribute('data-reduced-motion', 'true');
  const before = await loader.locator('svg').evaluate((svg) => svg.innerHTML);
  await page.waitForTimeout(250);
  expect(await loader.locator('svg').evaluate((svg) => svg.innerHTML)).toBe(before);
  pending.release();
  await ready(page);
});

test('editor contém foco e devolve ao acionador ao fechar', async ({ page }) => {
  await login(page);
  await ready(page);
  const { editor, opener } = await createAndOpen(page);
  const focusables = editor.locator('button:visible:not([disabled]), input:visible:not([disabled]), select:visible:not([disabled]), textarea:visible:not([disabled])');
  await focusables.last().focus();
  await page.keyboard.press('Tab');
  await expect(focusables.first()).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(focusables.last()).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(editor).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test('editor móvel apresenta navegação compacta sem overflow da página', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await ready(page);
  const { editor } = await createAndOpen(page);
  await expect(editor.getByLabel('Seção do orçamento')).toBeVisible();
  const saveBounds = await editor.getByRole('button', { name: 'Salvar revisão' }).boundingBox();
  expect(saveBounds.x).toBeGreaterThanOrEqual(0);
  expect(saveBounds.x + saveBounds.width).toBeLessThanOrEqual(390);
  const footerBounds = await editor.locator('.orc-editor-footer').boundingBox();
  expect(footerBounds.x + footerBounds.width).toBeLessThanOrEqual(390);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});


test('salvar mantém a carteira e não reapresenta o loader inicial', async ({ page }) => {
  await login(page);
  await ready(page);
  const { editor } = await createAndOpen(page);
  await editor.getByLabel('Dados da Contratante').fill('Cadastro UI');
  await editor.getByLabel('Escopo do Serviço').fill('Pintura');
  await editor.getByLabel('Modalidade do Trabalho').selectOption('Spot');
  await editor.getByLabel('Prazo de execução (dias)').fill('10');
  await expect(editor.getByLabel('Saldo de Mão de Obra')).toHaveCount(0);
  await editor.getByLabel('Estado', { exact: true }).selectOption('GO');
  await editor.getByLabel('Cidade', { exact: true }).selectOption('Goiânia');
  const pending = gate();
  let refreshing = false;
  await page.route('**/api/orcamento/orcamentos', async (route) => {
    refreshing = true;
    await pending.promise;
    await route.continue();
  });
  await editor.getByRole('button', { name: 'Salvar revisão' }).click();
  await expect.poll(() => refreshing).toBeTruthy();
  await expect(loaderFor(page)).toHaveCount(0);
  await expect(page.locator('.orc-portfolio')).toBeVisible();
  await expect(editor).toBeVisible();
  pending.release();
  await expect(editor).toHaveCount(0);
});


for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
  test(`modal bloqueia navegação externa em viewport ${viewport.width}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await login(page);
    await ready(page);
    await createAndOpen(page);
    await page.evaluate(() => window.scrollTo(0, 0));
    const externalControl = page.locator(viewport.width < 600 ? '.access-sidebar-trigger' : '.access-sidebar-item').first();
    const point = await externalControl.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
    });
    expect(point.y).toBeGreaterThan(0);
    expect(point.y).toBeLessThan(viewport.height);
    await expect.poll(() => page.evaluate(({ x, y }) => Boolean(
      document.elementFromPoint(x, y)?.closest('.orc-editor-layer'),
    ), point)).toBeTruthy();
  });
}

test('minimizar e restaurar preserva scroll vertical e horizontal da tabela', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await login(page);
  await ready(page);
  const { editor } = await createAndOpen(page);
  const form = editor.locator('.orc-editor-form');
  const table = editor.locator('.orc-table-scroll').first();
  await table.evaluate((element) => { element.scrollLeft = 130; });
  await form.evaluate((element) => { element.scrollTop = 400; });
  const left = await table.evaluate((element) => element.scrollLeft);
  const top = await form.evaluate((element) => element.scrollTop);
  expect(left).toBeGreaterThan(0);
  expect(top).toBeGreaterThan(0);
  await editor.getByRole('button', { name: 'Minimizar editor' }).click();
  await expect(form).toHaveCount(0);
  await editor.getByRole('button', { name: 'Restaurar editor' }).click();
  await expect.poll(() => form.evaluate((element) => element.scrollTop)).toBe(top);
  await expect.poll(() => table.evaluate((element) => element.scrollLeft)).toBe(left);
});


test('diálogo de situação contém foco e bloqueia Escape durante envio', async ({ page }) => {
  await login(page);
  await ready(page);
  const { editor } = await createAndOpen(page);
  const name = await editor.getAttribute('aria-label');
  await page.keyboard.press('Escape');
  await expect(editor).toHaveCount(0);
  const trigger = page.locator('.orc-card', { hasText: name }).getByRole('button', { name: 'Inativo', exact: true });
  await trigger.click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByLabel('Motivo da mudança')).toBeFocused();
  await dialog.getByRole('button', { name: 'Confirmar' }).focus();
  await page.keyboard.press('Tab');
  await expect(dialog.getByRole('button', { name: 'Fechar', exact: true })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(dialog.getByRole('button', { name: 'Confirmar' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await trigger.click();
  await dialog.getByLabel('Motivo da mudança').fill('Teste de interação');
  const pending = gate();
  let submitted = false;
  await page.route('**/api/orcamento/revisoes/*/situacao', async (route) => {
    submitted = true;
    await pending.promise;
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Falha de teste' }) });
  });
  await dialog.getByRole('button', { name: 'Confirmar' }).click();
  await expect.poll(() => submitted).toBeTruthy();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Cancelar' })).toBeDisabled();
  pending.release();
  await expect(dialog.getByRole('button', { name: 'Cancelar' })).toBeEnabled();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

for (const width of [1280, 390]) {
  test(`menu principal acompanha a rolagem em ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await login(page);
    await ready(page);
    // Guarantee a long page independently of the number of saved budgets.
    await page.locator('.access-app-main').evaluate((element) => { element.style.minHeight = '3000px'; });
    await page.evaluate(() => window.scrollTo(0, 900));
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(500);
    if (width < 900) await page.getByRole('button', { name: 'Abrir menu' }).click();
    const sidebar = page.getByRole('complementary', { name: 'Menu principal' });
    await expect(sidebar).toBeInViewport();
    await expect.poll(async () => (await sidebar.boundingBox()).y).toBe(0);
    await expect(sidebar.getByRole('button', { name: 'Orçamento', exact: true })).toBeInViewport();
    await expect(sidebar.getByRole('button', { name: 'Sair', exact: true })).toBeInViewport();
    if (width >= 900) {
      const menuBounds = await sidebar.boundingBox();
      const contentBounds = await page.locator('.access-app-main').boundingBox();
      expect(contentBounds.x).toBeGreaterThanOrEqual(menuBounds.x + menuBounds.width);
    }
  });
}

test('carteira filtra por busca, confirma nova revisão e abre histórico em gaveta', async ({ page }) => {
  await login(page);
  await ready(page);
  const name = `UI carteira ${Date.now()}`;
  await page.locator('.orc-create-window').getByLabel('Contratante', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Criar orçamento', exact: true }).click();
  const card = page.locator('.orc-card', { hasText: name });
  await expect(card).toBeVisible();

  const search = page.getByLabel('Buscar orçamentos');
  await search.fill('contratante-inexistente-xyz');
  await expect(page.getByRole('heading', { name: 'Nenhum orçamento encontrado' })).toBeVisible();
  await page.getByRole('button', { name: 'Limpar filtros' }).click();
  await expect(search).toHaveValue('');
  await search.fill(name.toUpperCase());
  await expect(card).toBeVisible();
  await expect(page.locator('.orc-card')).toHaveCount(1);

  await card.getByRole('button', { name: 'Mais ações' }).click();
  await card.getByRole('button', { name: 'Nova revisão' }).click();
  const confirm = page.getByRole('dialog', { name: 'Criar nova revisão' });
  await expect(confirm).toBeVisible();
  await confirm.getByRole('button', { name: 'Cancelar' }).click();
  await expect(confirm).toHaveCount(0);

  await card.getByRole('button', { name: 'Histórico de edição' }).click();
  const drawer = page.getByRole('dialog', { name: 'Histórico de edição' });
  await expect(drawer).toBeVisible();
  await expect(page.locator('body')).toHaveAttribute('data-orc-modal-open', /.*/);
  await page.keyboard.press('Escape');
  await expect(drawer).toHaveCount(0);
  await expect(page.locator('body')).not.toHaveAttribute('data-orc-modal-open', /.*/);
});
