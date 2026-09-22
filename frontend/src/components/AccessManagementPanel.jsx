import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  KeyRound,
  Loader2,
  Save,
  ShieldCheck,
  UserPlus,
  Users,
} from 'lucide-react';
import { createAuthClient } from '../auth/authClient';
import {
  buildCreateUserPayload,
  buildUserPatch,
  createEmptyUserForm,
  getManagedUserRestrictions,
  normalizeManagedUsers,
  PERMISSION_OPTIONS,
  togglePermission,
  updateManagedUser,
  validateUserForm,
} from './accessControlModel';
import '../styles/access-control.css';

function PermissionFields({ permissions, onChange, disabled = false, labelledBy }) {
  return (
    <div className="access-permission-grid" role="group" aria-labelledby={labelledBy}>
      {PERMISSION_OPTIONS.map((permission) => (
        <label className="access-permission-option" key={permission.id}>
          <input
            type="checkbox"
            checked={permissions.includes(permission.id)}
            onChange={() => onChange(togglePermission(permissions, permission.id))}
            disabled={disabled}
          />
          <span>{permission.label}</span>
        </label>
      ))}
    </div>
  );
}

export default function AccessManagementPanel({
  apiBase = '/api',
  csrfToken,
  onNotify,
  onBusyChange,
}) {
  const client = useMemo(() => createAuthClient({ apiBase }), [apiBase]);
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState(createEmptyUserForm);
  const [formErrors, setFormErrors] = useState({});
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [savingUserId, setSavingUserId] = useState(null);
  const [error, setError] = useState(null);
  const busy = loading || creating || savingUserId !== null;

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(normalizeManagedUsers(await client.listUsers()));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    onBusyChange?.(busy);
  }, [busy, onBusyChange]);

  useEffect(() => () => onBusyChange?.(false), [onBusyChange]);

  const updateForm = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
    setFormErrors((current) => {
      if (!current[field]) return current;
      const { [field]: _removed, ...remaining } = current;
      return remaining;
    });
  };

  const handleCreateUser = async (event) => {
    event.preventDefault();
    const validation = validateUserForm(form);
    setFormErrors(validation);
    if (Object.keys(validation).length > 0 || creating) return;

    setCreating(true);
    setError(null);
    try {
      await client.createUser(buildCreateUserPayload(form), csrfToken);
      setForm(createEmptyUserForm());
      await loadUsers();
      onNotify?.({ type: 'success', message: 'Usuario criado com os acessos selecionados.' });
    } catch (requestError) {
      setError(requestError.message);
      onNotify?.({ type: 'error', message: requestError.message });
    } finally {
      setCreating(false);
    }
  };

  const changeManagedUser = (userId, patch) => {
    setUsers((current) => updateManagedUser(current, userId, patch));
  };

  const handleSaveUser = async (user) => {
    if (savingUserId) return;
    setSavingUserId(user.id);
    setError(null);
    try {
      await client.updateUser(user.id, buildUserPatch(user), csrfToken);
      await loadUsers();
      onNotify?.({ type: 'success', message: `Acessos de ${user.displayName} atualizados.` });
    } catch (requestError) {
      setError(requestError.message);
      onNotify?.({ type: 'error', message: requestError.message });
    } finally {
      setSavingUserId(null);
    }
  };

  return (
    <section className="access-management" aria-labelledby="access-management-title">
      <header className="access-management-hero">
        <div className="access-management-icon"><Users size={24} aria-hidden="true" /></div>
        <div>
          <span className="access-kicker">Administracao</span>
          <h1 id="access-management-title">Usuarios e acessos</h1>
          <p>Crie usuarios e escolha exatamente quais paineis aparecem para cada pessoa.</p>
        </div>
      </header>

      {error && (
        <p className="access-feedback access-feedback-error" role="alert">{error}</p>
      )}

      <form className="access-create-card" onSubmit={handleCreateUser} noValidate>
        <div className="access-card-heading">
          <UserPlus size={20} aria-hidden="true" />
          <div>
            <h2>Novo usuario</h2>
            <p>A senha e temporaria e deve ser entregue por um canal seguro.</p>
          </div>
        </div>

        <div className="access-form-grid">
          <label className="access-field">
            <span>Nome de usuario</span>
            <input
              type="text"
              autoComplete="off"
              value={form.username}
              onChange={(event) => updateForm('username', event.target.value)}
              aria-invalid={Boolean(formErrors.username)}
              aria-describedby={formErrors.username ? 'new-user-username-error' : undefined}
            />
            {formErrors.username && <small id="new-user-username-error">{formErrors.username}</small>}
          </label>

          <label className="access-field">
            <span>Nome de exibicao</span>
            <input
              type="text"
              autoComplete="name"
              value={form.displayName}
              onChange={(event) => updateForm('displayName', event.target.value)}
              aria-invalid={Boolean(formErrors.displayName)}
              aria-describedby={formErrors.displayName ? 'new-user-name-error' : undefined}
            />
            {formErrors.displayName && <small id="new-user-name-error">{formErrors.displayName}</small>}
          </label>

          <label className="access-field">
            <span>Senha inicial</span>
            <div className="access-input-with-icon">
              <KeyRound size={16} aria-hidden="true" />
              <input
                type="password"
                autoComplete="new-password"
                value={form.password}
                onChange={(event) => updateForm('password', event.target.value)}
                aria-invalid={Boolean(formErrors.password)}
                aria-describedby={formErrors.password ? 'new-user-password-error' : undefined}
              />
            </div>
            {formErrors.password && <small id="new-user-password-error">{formErrors.password}</small>}
          </label>

          <label className="access-active-toggle">
            <input
              type="checkbox"
              checked={form.active}
              onChange={(event) => updateForm('active', event.target.checked)}
            />
            <span>Criar usuario ativo</span>
          </label>

          <label className="access-active-toggle">
            <input
              type="checkbox"
              checked={form.mustChangePassword}
              onChange={(event) => updateForm('mustChangePassword', event.target.checked)}
            />
            <span>Exigir troca da senha no primeiro acesso</span>
          </label>
        </div>

        <fieldset className="access-permission-fieldset">
          <legend id="new-user-permissions">Paineis liberados</legend>
          <PermissionFields
            permissions={form.permissions}
            onChange={(permissions) => updateForm('permissions', permissions)}
            labelledBy="new-user-permissions"
          />
          {formErrors.permissions && <small>{formErrors.permissions}</small>}
        </fieldset>

        <button className="access-primary-button" type="submit" disabled={creating}>
          {creating ? <Loader2 className="access-spin" size={17} aria-hidden="true" /> : <UserPlus size={17} aria-hidden="true" />}
          {creating ? 'Criando...' : 'Criar usuario'}
        </button>
      </form>

      <div className="access-user-list-heading">
        <div>
          <span className="access-kicker">Equipe</span>
          <h2>Usuarios cadastrados</h2>
        </div>
        <span className="access-count" aria-label={`${users.length} usuarios`}>{users.length}</span>
      </div>

      {loading && users.length === 0 && (
        <p className="access-loading" role="status">
          <Loader2 className="access-spin" size={18} aria-hidden="true" /> Carregando usuarios...
        </p>
      )}

      {!loading && users.length === 0 && !error && (
        <p className="access-empty-state">Nenhum usuario cadastrado.</p>
      )}

      <div className="access-user-list">
        {users.map((user) => {
          const permissionTitleId = `permissions-${user.id}`;
          const saving = savingUserId === user.id;
          const restrictions = getManagedUserRestrictions(user);
          return (
            <article className="access-user-card" key={user.id}>
              <header>
                <div className="access-user-identity">
                  <span aria-hidden="true">{user.displayName.slice(0, 1).toUpperCase()}</span>
                  <div>
                    <h3>{user.displayName}</h3>
                    <p>@{user.username}</p>
                  </div>
                </div>
                {user.isSystemOwner && (
                  <span className="access-owner-badge"><ShieldCheck size={14} aria-hidden="true" /> Administrador principal</span>
                )}
              </header>

              <label className="access-field access-user-display-name">
                <span>Nome de exibicao</span>
                <input
                  type="text"
                  value={user.displayName}
                  onChange={(event) => changeManagedUser(user.id, { displayName: event.target.value })}
                />
              </label>

              <div className="access-user-status-row">
                <label className="access-active-toggle">
                  <input
                    type="checkbox"
                    checked={user.active}
                    disabled={!restrictions.canChangeActive}
                    onChange={(event) => changeManagedUser(user.id, { active: event.target.checked })}
                  />
                  <span>{user.active ? 'Usuario ativo' : 'Usuario desativado'}</span>
                </label>
                {user.isSystemOwner && <small>O administrador principal nao pode ser desativado.</small>}
              </div>

              <fieldset className="access-permission-fieldset">
                <legend id={permissionTitleId}>Acessos</legend>
                <PermissionFields
                  permissions={user.permissions}
                  onChange={(permissions) => changeManagedUser(user.id, { permissions })}
                  labelledBy={permissionTitleId}
                  disabled={!restrictions.canChangePermissions}
                />
                {!restrictions.canChangePermissions && (
                  <small>Os acessos do administrador principal sao protegidos.</small>
                )}
              </fieldset>

              <button
                className="access-secondary-button"
                type="button"
                onClick={() => handleSaveUser(user)}
                disabled={saving || !user.displayName.trim() || user.permissions.length === 0}
              >
                {saving ? <Loader2 className="access-spin" size={17} aria-hidden="true" /> : <Save size={17} aria-hidden="true" />}
                {saving ? 'Salvando...' : 'Salvar alteracoes'}
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
