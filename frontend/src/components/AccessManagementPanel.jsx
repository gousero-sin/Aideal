import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  KeyRound,
  Loader2,
  Save,
  ShieldCheck,
  Trash2,
  UserPlus,
  Users,
} from 'lucide-react';
import { createAuthClient } from '../auth/authClient';
import {
  buildCreateUserPayload,
  buildPasswordResetPatch,
  buildUserPatch,
  createEmptyUserForm,
  getManagedUserRestrictions,
  normalizeManagedUsers,
  PERMISSION_OPTIONS,
  togglePermission,
  updateManagedUser,
  validateResetPassword,
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
  currentUserId,
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
  const [actionUserId, setActionUserId] = useState(null);
  const [resetUserId, setResetUserId] = useState(null);
  const [resetPassword, setResetPassword] = useState('');
  const [resetPasswordError, setResetPasswordError] = useState(null);
  const [deleteUserId, setDeleteUserId] = useState(null);
  const [error, setError] = useState(null);
  const busy = loading || creating || savingUserId !== null || actionUserId !== null;
  // Recargas depois de salvar não cobrem a tela: só a primeira leitura e as gravações.
  const [loadedOnce, setLoadedOnce] = useState(false);
  const screenBusy = (loading && !loadedOnce) || creating || savingUserId !== null || actionUserId !== null;

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(normalizeManagedUsers(await client.listUsers()));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
      setLoadedOnce(true);
    }
  }, [client]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    onBusyChange?.(screenBusy);
  }, [screenBusy, onBusyChange]);

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
    if (busy) return;
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

  const closePasswordReset = () => {
    setResetUserId(null);
    setResetPassword('');
    setResetPasswordError(null);
  };

  const openPasswordReset = (userId) => {
    closePasswordReset();
    setDeleteUserId(null);
    setResetUserId(userId);
  };

  const handleResetPassword = async (event, user) => {
    event.preventDefault();
    const validationError = validateResetPassword(resetPassword);
    setResetPasswordError(validationError);
    if (validationError || busy) return;

    setActionUserId(user.id);
    setError(null);
    try {
      await client.updateUser(user.id, buildPasswordResetPatch(resetPassword), csrfToken);
      closePasswordReset();
      onNotify?.({ type: 'success', message: `Senha de ${user.displayName} redefinida. A troca sera exigida no proximo acesso.` });
    } catch {
      const message = 'Nao foi possivel redefinir a senha. Tente novamente.';
      setError(message);
      onNotify?.({ type: 'error', message });
    } finally {
      setActionUserId(null);
    }
  };

  const handleDeleteUser = async (user) => {
    if (busy || deleteUserId !== user.id) return;
    setActionUserId(user.id);
    setError(null);
    try {
      await client.deleteUser(user.id, csrfToken);
      setDeleteUserId(null);
      closePasswordReset();
      await loadUsers();
      onNotify?.({ type: 'success', message: `Usuario ${user.displayName} excluido.` });
    } catch {
      const message = 'Nao foi possivel excluir o usuario. Tente novamente.';
      setError(message);
      onNotify?.({ type: 'error', message });
    } finally {
      setActionUserId(null);
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
          const restrictions = getManagedUserRestrictions(user, currentUserId);
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
                disabled={busy || !user.displayName.trim() || user.permissions.length === 0}
              >
                {saving ? <Loader2 className="access-spin" size={17} aria-hidden="true" /> : <Save size={17} aria-hidden="true" />}
                {saving ? 'Salvando...' : 'Salvar alteracoes'}
              </button>

              {(restrictions.canResetPassword || restrictions.canDelete) && (
                <div className="access-account-actions">
                  {restrictions.canResetPassword && (
                    <button
                      className="access-secondary-button"
                      type="button"
                      onClick={() => openPasswordReset(user.id)}
                      disabled={busy}
                    >
                      <KeyRound size={17} aria-hidden="true" /> Redefinir senha
                    </button>
                  )}
                  {restrictions.canDelete && (
                    <button
                      className="access-secondary-button access-danger-button"
                      type="button"
                      onClick={() => { closePasswordReset(); setDeleteUserId(user.id); }}
                      disabled={busy}
                    >
                      <Trash2 size={17} aria-hidden="true" /> Excluir usuario
                    </button>
                  )}
                </div>
              )}

              {resetUserId === user.id && restrictions.canResetPassword && (
                <form className="access-inline-action" onSubmit={(event) => handleResetPassword(event, user)} noValidate>
                  <label className="access-field">
                    <span>Nova senha temporaria para {user.displayName}</span>
                    <input
                      type="password"
                      autoComplete="new-password"
                      minLength={10}
                      value={resetPassword}
                      onChange={(event) => { setResetPassword(event.target.value); setResetPasswordError(null); }}
                      aria-invalid={Boolean(resetPasswordError)}
                      aria-describedby={resetPasswordError ? `reset-password-error-${user.id}` : undefined}
                    />
                    {resetPasswordError && <small id={`reset-password-error-${user.id}`}>{resetPasswordError}</small>}
                  </label>
                  <p>Entregue a senha por um canal seguro. O usuario precisara troca-la no proximo acesso.</p>
                  <div className="access-account-actions">
                    <button className="access-secondary-button" type="button" onClick={closePasswordReset} disabled={busy}>Cancelar</button>
                    <button className="access-primary-button" type="submit" disabled={busy}>
                      {actionUserId === user.id ? 'Redefinindo...' : 'Confirmar nova senha'}
                    </button>
                  </div>
                </form>
              )}

              {deleteUserId === user.id && restrictions.canDelete && (
                <div className="access-inline-action" role="group" aria-label={`Confirmar exclusao de ${user.displayName}`}>
                  <p>Excluir {user.displayName} permanentemente? Essa acao nao pode ser desfeita.</p>
                  <div className="access-account-actions">
                    <button className="access-secondary-button" type="button" onClick={() => setDeleteUserId(null)} disabled={busy}>Cancelar</button>
                    <button className="access-secondary-button access-danger-button" type="button" onClick={() => handleDeleteUser(user)} disabled={busy}>
                      {actionUserId === user.id ? 'Excluindo...' : 'Confirmar exclusao'}
                    </button>
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
