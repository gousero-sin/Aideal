import test from 'node:test';
import assert from 'node:assert/strict';

import {
  MIN_PASSWORD_LENGTH,
  buildPasswordChangePayload,
  validatePasswordChange,
} from '../auth/passwordChangeModel.js';

test('rejeita senha atual vazia, senha curta e confirmacao divergente', () => {
  assert.deepEqual(validatePasswordChange({
    currentPassword: '',
    newPassword: 'curta',
    confirmation: 'diferente',
  }), {
    currentPassword: 'Informe a senha temporaria.',
    newPassword: `A nova senha deve ter pelo menos ${MIN_PASSWORD_LENGTH} caracteres.`,
    confirmation: 'A confirmacao deve ser igual a nova senha.',
  });
});

test('aceita exatamente dez caracteres e cria payload sem a confirmacao', () => {
  const form = {
    currentPassword: 'temporaria',
    newPassword: '1234567890',
    confirmation: '1234567890',
  };

  assert.deepEqual(validatePasswordChange(form), {});
  assert.deepEqual(buildPasswordChangePayload(form), {
    currentPassword: 'temporaria',
    newPassword: '1234567890',
  });
});

test('payload nao e criado enquanto o formulario for invalido', () => {
  assert.equal(buildPasswordChangePayload({
    currentPassword: 'temporaria',
    newPassword: '123456789',
    confirmation: '123456789',
  }), null);
});
