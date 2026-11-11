import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'line',
  use: {
    baseURL: 'http://127.0.0.1:8011',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: '../backend/.venv/bin/python -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8011',
    url: 'http://127.0.0.1:8011/health',
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      AIDEAL_ADMIN_USERNAME: 'Eduardo',
      AIDEAL_DB_PATH: '/tmp/aideal-goflow-e2e-financeiro.db',
      AIDEAL_ADMIN_PASSWORD: 'senha-admin-e2e-segura',
      AIDEAL_IDENTITY_DB_PATH: '/tmp/aideal-goflow-e2e-identity.db',
      AIDEAL_ORCAMENTO_DB_PATH: '/tmp/aideal-goflow-e2e-orcamento.db',
      AIDEAL_ADMIN_COOKIE_SECURE: 'false',
    },
  },
});
