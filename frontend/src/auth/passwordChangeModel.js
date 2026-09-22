export const MIN_PASSWORD_LENGTH = 10;

export const EMPTY_PASSWORD_CHANGE_FORM = Object.freeze({
  currentPassword: '',
  newPassword: '',
  confirmation: '',
});

export const validatePasswordChange = (form) => {
  const errors = {};

  if (!form?.currentPassword) {
    errors.currentPassword = 'Informe a senha temporaria.';
  }
  if (!form?.newPassword || form.newPassword.length < MIN_PASSWORD_LENGTH) {
    errors.newPassword = `A nova senha deve ter pelo menos ${MIN_PASSWORD_LENGTH} caracteres.`;
  }
  if (form?.confirmation !== form?.newPassword) {
    errors.confirmation = 'A confirmacao deve ser igual a nova senha.';
  }

  return errors;
};

export const buildPasswordChangePayload = (form) => {
  if (Object.keys(validatePasswordChange(form)).length > 0) return null;
  return {
    currentPassword: form.currentPassword,
    newPassword: form.newPassword,
  };
};
