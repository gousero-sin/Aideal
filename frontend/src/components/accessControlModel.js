export const MODULE_CATALOG = Object.freeze([
  Object.freeze({ id: 'dre', label: 'Painel DRE', permission: 'dre.view' }),
  Object.freeze({ id: 'fluxo_caixa', label: 'Painel Fluxo', permission: 'fluxo.view' }),
  Object.freeze({ id: 'admin_banco', label: 'Admin Banco', permission: 'admin_banco.use' }),
  Object.freeze({ id: 'usuarios', label: 'Usuarios e acessos', permission: 'users.manage' }),
  Object.freeze({ id: 'orcamento', label: 'Orçamento', permission: 'orcamento.view' }),
]);

export const PERMISSION_OPTIONS = Object.freeze([
  Object.freeze({ id: 'dre.view', label: 'Visualizar Painel DRE' }),
  Object.freeze({ id: 'fluxo.view', label: 'Visualizar Painel Fluxo de Caixa' }),
  Object.freeze({ id: 'admin_banco.use', label: 'Usar operacoes do Admin Banco' }),
  Object.freeze({ id: 'users.manage', label: 'Gerenciar usuarios e acessos' }),
  Object.freeze({ id: 'orcamento.view', label: 'Visualizar Orcamento' }),
  Object.freeze({ id: 'orcamento.edit', label: 'Criar e editar Orcamento' }),
  Object.freeze({ id: 'orcamento.transition', label: 'Alterar situacao do Orcamento' }),
]);

const toUniqueStrings = (values) => [
  ...new Set((Array.isArray(values) ? values : []).filter((value) => (
    typeof value === 'string' && value.trim()
  ))),
];

const resolveModule = (module) => {
  const descriptor = typeof module === 'string' ? { id: module } : module;
  if (!descriptor?.id || descriptor.enabled === false) return null;
  const catalogModule = MODULE_CATALOG.find(({ id }) => id === descriptor.id);
  if (!catalogModule && !descriptor.permission) return null;
  return {
    ...catalogModule,
    ...descriptor,
    id: String(descriptor.id),
    permission: descriptor.permission || catalogModule?.permission,
  };
};

export const filterAccessibleModules = (modules, permissions) => {
  const permissionSet = new Set(toUniqueStrings(permissions));
  return (Array.isArray(modules) ? modules : [])
    .map(resolveModule)
    .filter((module) => module && permissionSet.has(module.permission));
};

export const togglePermission = (permissions, permission) => {
  const current = toUniqueStrings(permissions);
  return current.includes(permission)
    ? current.filter((candidate) => candidate !== permission)
    : [...current, permission];
};

export const createEmptyUserForm = () => ({
  username: '',
  displayName: '',
  password: '',
  permissions: [],
  active: true,
  mustChangePassword: true,
});

export const PASSWORD_MIN_LENGTH_MESSAGE = 'A senha inicial deve ter pelo menos 10 caracteres.';

export const validateUserForm = (form) => ({
  ...(!form?.username?.trim() ? { username: 'Informe o nome de usuario.' } : {}),
  ...(!form?.displayName?.trim() ? { displayName: 'Informe o nome de exibicao.' } : {}),
  ...((form?.password?.length || 0) < 10
    ? { password: PASSWORD_MIN_LENGTH_MESSAGE }
    : {}),
  ...(!Array.isArray(form?.permissions) || form.permissions.length === 0
    ? { permissions: 'Selecione ao menos um acesso.' }
    : {}),
});

export const buildCreateUserPayload = (form) => ({
  username: form.username.trim(),
  display_name: form.displayName.trim(),
  password: form.password,
  permissions: toUniqueStrings(form.permissions),
  active: form.active !== false,
  must_change_password: form.mustChangePassword !== false,
});

export const normalizeManagedUsers = (payload) => {
  const records = Array.isArray(payload)
    ? payload
    : (payload?.users || payload?.data || []);

  return (Array.isArray(records) ? records : []).filter((user) => user?.id).map((user) => ({
    id: String(user.id),
    username: String(user.username || ''),
    displayName: String(user.display_name || user.displayName || user.username || ''),
    active: user.active !== false,
    isSystemOwner: user.is_system_owner === true || user.isSystemOwner === true,
    permissions: toUniqueStrings(user.permissions),
    createdAt: user.created_at || user.createdAt || null,
    updatedAt: user.updated_at || user.updatedAt || null,
  }));
};

export const updateManagedUser = (users, userId, patch) => (
  (Array.isArray(users) ? users : []).map((user) => (
    user.id === userId ? { ...user, ...patch } : user
  ))
);

export const getManagedUserRestrictions = (user) => ({
  canChangeActive: user?.isSystemOwner !== true,
  canChangePermissions: user?.isSystemOwner !== true,
});

export const buildUserPatch = (user, patch = {}) => ({
  display_name: String(patch.displayName ?? user.displayName).trim(),
  active: patch.active ?? user.active,
  permissions: toUniqueStrings(patch.permissions ?? user.permissions),
});
