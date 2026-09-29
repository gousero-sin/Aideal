import test from 'node:test';
import assert from 'node:assert/strict';

import {
  PASSWORD_MIN_LENGTH_MESSAGE,
  PERMISSION_OPTIONS,
  buildCreateUserPayload,
  buildUserPatch,
  buildPasswordResetPatch,
  createEmptyUserForm,
  filterAccessibleModules,
  getManagedUserRestrictions,
  normalizeManagedUsers,
  togglePermission,
  updateManagedUser,
  validateUserForm,
  validateResetPassword,
} from './accessControlModel.js';

test('separa leitura, edição e transição do orçamento', () => {
  const permissionIds = PERMISSION_OPTIONS.map(({ id }) => id);

  assert.ok(permissionIds.includes('orcamento.view'));
  assert.ok(permissionIds.includes('orcamento.edit'));
  assert.ok(permissionIds.includes('orcamento.transition'));
});

test('filtra modulos pela lista liberada e pela permissao efetiva', () => {
  const visible = filterAccessibleModules(
    ['dre', 'fluxo_caixa', 'usuarios'],
    ['dre.view', 'users.manage'],
  );

  assert.deepEqual(visible.map(({ id }) => id), ['dre', 'usuarios']);
});

test('nega todos os modulos quando a sessao nao informa acessos', () => {
  assert.deepEqual(filterAccessibleModules(undefined, undefined), []);
  assert.deepEqual(filterAccessibleModules([], ['dre.view']), []);
});

test('preserva descritores de modulo fornecidos pelo servidor sem confiar na permissao ausente', () => {
  const visible = filterAccessibleModules(
    [{ id: 'orcamento', label: 'Orcamento 2027', permission: 'orcamento.view' }],
    ['orcamento.view'],
  );

  assert.equal(visible[0].label, 'Orcamento 2027');
  assert.equal(visible[0].id, 'orcamento');
});

test('alterna permissao criando uma nova lista', () => {
  const initial = ['dre.view'];
  const added = togglePermission(initial, 'fluxo.view');
  const removed = togglePermission(added, 'dre.view');

  assert.deepEqual(initial, ['dre.view']);
  assert.deepEqual(added, ['dre.view', 'fluxo.view']);
  assert.deepEqual(removed, ['fluxo.view']);
  assert.notEqual(added, initial);
});

test('normaliza resposta de usuarios em lista ou envelope', () => {
  const user = {
    id: 'u-1',
    username: 'maria',
    display_name: 'Maria',
    active: true,
    permissions: ['dre.view', 'dre.view'],
  };

  assert.deepEqual(normalizeManagedUsers([user]), normalizeManagedUsers({ users: [user] }));
  assert.deepEqual(normalizeManagedUsers({ data: [user] })[0].permissions, ['dre.view']);
});

test('valida campos obrigatorios e senha inicial', () => {
  assert.deepEqual(validateUserForm(createEmptyUserForm()), {
    username: 'Informe o nome de usuario.',
    displayName: 'Informe o nome de exibicao.',
    password: PASSWORD_MIN_LENGTH_MESSAGE,
    permissions: 'Selecione ao menos um acesso.',
  });

  assert.deepEqual(validateUserForm({
    username: '  maria ',
    displayName: ' Maria ',
    password: 'segura12345',
    permissions: ['dre.view'],
    active: true,
    mustChangePassword: true,
  }), {});
});

test('monta patch sem senha e sem mutar usuario original', () => {
  const original = {
    displayName: 'Maria',
    active: true,
    permissions: ['dre.view'],
  };
  const patch = buildUserPatch(original, { active: false, permissions: ['fluxo.view'] });

  assert.deepEqual(patch, {
    display_name: 'Maria',
    active: false,
    permissions: ['fluxo.view'],
  });
  assert.equal(original.active, true);
});

test('monta payload de criacao normalizado', () => {
  assert.deepEqual(buildCreateUserPayload({
    username: '  joao ',
    displayName: ' Joao Silva ',
    password: 'senha123',
    permissions: ['dre.view', 'dre.view'],
    active: false,
    mustChangePassword: true,
  }), {
    username: 'joao',
    display_name: 'Joao Silva',
    password: 'senha123',
    permissions: ['dre.view'],
    active: false,
    must_change_password: true,
  });
});

test('atualiza somente o usuario alvo sem mutar a lista', () => {
  const users = [{ id: 'u-1', active: true }, { id: 'u-2', active: true }];
  const updated = updateManagedUser(users, 'u-1', { active: false });

  assert.equal(users[0].active, true);
  assert.equal(updated[0].active, false);
  assert.equal(updated[1], users[1]);
});

test('ignora modulos desconhecidos, desativados e descritores incompletos', () => {
  assert.deepEqual(filterAccessibleModules([
    'desconhecido',
    { id: 'dre', enabled: false },
    null,
  ], ['dre.view']), []);
});

test('impede auto-bloqueio do administrador principal na interface', () => {
  assert.deepEqual(getManagedUserRestrictions({ isSystemOwner: true }), {
    canChangeActive: false,
    canChangePermissions: false,
    canResetPassword: false,
    canDelete: false,
  });
  assert.deepEqual(getManagedUserRestrictions({ isSystemOwner: false }), {
    canChangeActive: true,
    canChangePermissions: true,
    canResetPassword: true,
    canDelete: true,
  });
  assert.equal(getManagedUserRestrictions({ id: 'u-1' }, 'u-1').canDelete, false);
  assert.equal(getManagedUserRestrictions({ id: 'u-1' }, 'u-1').canResetPassword, false);
});

test('valida senha temporaria de redefinicao e envia somente a senha', () => {
  assert.equal(validateResetPassword('curta'), 'A senha temporaria deve ter pelo menos 10 caracteres.');
  assert.equal(validateResetPassword('abcdefghij'), null);
  assert.deepEqual(buildPasswordResetPatch('abcdefghij'), { password: 'abcdefghij' });
});
