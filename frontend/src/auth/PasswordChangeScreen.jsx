import React, { useMemo, useState } from 'react';
import { KeyRound, Loader2, ShieldCheck } from 'lucide-react';
import { useAuth } from './AuthContext';
import {
  EMPTY_PASSWORD_CHANGE_FORM,
  MIN_PASSWORD_LENGTH,
  buildPasswordChangePayload,
  validatePasswordChange,
} from './passwordChangeModel';
import '../styles/access-control.css';

const errorIdFor = (field) => `password-change-${field}-error`;

export default function PasswordChangeScreen() {
  const { changePassword, status, error: sessionError } = useAuth();
  const [form, setForm] = useState({ ...EMPTY_PASSWORD_CHANGE_FORM });
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const errors = useMemo(() => validatePasswordChange(form), [form]);
  const busy = submitting || status === 'loading';

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (busy) return;

    setSubmitted(true);
    setSubmitError(null);
    const payload = buildPasswordChangePayload(form);
    if (!payload) return;

    setSubmitting(true);
    try {
      await changePassword(payload);
      setForm({ ...EMPTY_PASSWORD_CHANGE_FORM });
      setSubmitted(false);
    } catch (requestError) {
      setSubmitError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  };

  const fieldError = (field) => (submitted ? errors[field] : null);

  return (
    <main className="access-login-shell">
      <section className="access-login-card" aria-labelledby="password-change-title">
        <div className="access-login-brand">
          <img src="/logo-aideal-peq-2.png" alt="AIDEAL Engenharia de Superficie" />
          <span><ShieldCheck size={18} aria-hidden="true" /> Primeiro acesso protegido</span>
        </div>

        <div className="access-login-heading">
          <KeyRound size={28} aria-hidden="true" />
          <div>
            <h1 id="password-change-title">Crie sua senha definitiva</h1>
            <p>A senha temporaria precisa ser substituida antes de continuar.</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} noValidate aria-busy={busy}>
          <label className="access-field" htmlFor="current-password">
            <span>Senha atual (temporaria)</span>
            <input
              id="current-password"
              name="currentPassword"
              type="password"
              autoComplete="current-password"
              value={form.currentPassword}
              onChange={(event) => updateField('currentPassword', event.target.value)}
              aria-invalid={Boolean(fieldError('currentPassword'))}
              aria-describedby={fieldError('currentPassword') ? errorIdFor('currentPassword') : undefined}
              disabled={busy}
              required
              autoFocus
            />
          </label>
          {fieldError('currentPassword') && (
            <p id={errorIdFor('currentPassword')} className="access-feedback access-feedback-error">
              {fieldError('currentPassword')}
            </p>
          )}

          <label className="access-field" htmlFor="new-password">
            <span>Nova senha</span>
            <input
              id="new-password"
              name="newPassword"
              type="password"
              autoComplete="new-password"
              minLength={MIN_PASSWORD_LENGTH}
              value={form.newPassword}
              onChange={(event) => updateField('newPassword', event.target.value)}
              aria-invalid={Boolean(fieldError('newPassword'))}
              aria-describedby={fieldError('newPassword')
                ? `new-password-help ${errorIdFor('newPassword')}`
                : 'new-password-help'}
              disabled={busy}
              required
            />
          </label>
          <p id="new-password-help">Use pelo menos {MIN_PASSWORD_LENGTH} caracteres.</p>
          {fieldError('newPassword') && (
            <p id={errorIdFor('newPassword')} className="access-feedback access-feedback-error">
              {fieldError('newPassword')}
            </p>
          )}

          <label className="access-field" htmlFor="password-confirmation">
            <span>Confirme a nova senha</span>
            <input
              id="password-confirmation"
              name="confirmation"
              type="password"
              autoComplete="new-password"
              value={form.confirmation}
              onChange={(event) => updateField('confirmation', event.target.value)}
              aria-invalid={Boolean(fieldError('confirmation'))}
              aria-describedby={fieldError('confirmation') ? errorIdFor('confirmation') : undefined}
              disabled={busy}
              required
            />
          </label>
          {fieldError('confirmation') && (
            <p id={errorIdFor('confirmation')} className="access-feedback access-feedback-error">
              {fieldError('confirmation')}
            </p>
          )}

          {(submitError || sessionError) && (
            <p className="access-feedback access-feedback-error" role="alert">
              {submitError || sessionError}
            </p>
          )}

          <button className="access-primary-button" type="submit" disabled={busy}>
            {busy ? <Loader2 className="access-spin" size={17} aria-hidden="true" /> : <KeyRound size={17} aria-hidden="true" />}
            {busy ? 'Atualizando...' : 'Definir nova senha'}
          </button>
        </form>
      </section>
    </main>
  );
}
