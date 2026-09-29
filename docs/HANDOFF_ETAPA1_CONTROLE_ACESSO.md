# Handoff — Etapa 1: controle de acesso do GoFlow

Atualizado em: 2026-09-29

## Atualização — 2026-09-29

- O Controle de Acessos permite redefinir a senha temporária de usuários comuns.
  A operação usa `PATCH /api/admin/users/{id}`, revoga as sessões abertas e exige
  troca da senha no próximo acesso. A senha do administrador principal só pode
  ser alterada pelo próprio usuário no fluxo de troca de senha.
- A exclusão de usuários comuns usa `DELETE /api/admin/users/{id}`, com sessão,
  permissão `users.manage` e token CSRF. O administrador principal e o próprio
  gestor não podem ser excluídos. Sessões e permissões do usuário excluído são
  removidas na mesma transação, e o evento `user.deleted` conserva o ID e nome
  de usuário na auditoria. Eventos anteriores preservam os IDs históricos em
  `deleted_actor_user_id` e `deleted_target_user_id` no metadata.
- Gestores com troca obrigatória de senha pendente não podem gerenciar usuários.
  A própria senha do gestor só pode ser trocada no fluxo que exige a senha atual;
  uma revogação concorrente de `users.manage` também bloqueia exclusão e reset.
- O painel exige confirmação antes de excluir. O CORS permite `DELETE` para
  atender à nova rota.

Este documento é uma lista operacional para continuar a implementação caso a sessão atual seja interrompida. O pedido do usuário é concluir a Etapa 1: login global, usuários administrados por Eduardo, permissões por painel e migração das abas superiores para um menu lateral.

## Regras obrigatórias

- Trabalhar em TDD: registrar RED, implementar GREEN, refatorar e medir cobertura mínima de 80%.
- Toda autorização deve ser aplicada no backend; esconder o item do menu não é uma barreira de segurança.
- Negar acesso por padrão.
- Não alterar nem apagar a modificação preexistente em `outputs/aideal_conferencia_20260717/~$latorio_Conferencia_Fluxo_Caixa_AIDEAL_2026.docx`.
- Não versionar bancos de identidade, senhas, hashes, cookies ou tokens.
- Usar `apply_patch` para edições manuais.

## Concluído

- [x] Plano técnico, matriz de permissões e revisão de ameaças.
- [x] Testes RED de integração em `backend/tests/test_access_control_api.py`.
- [x] Domínio de identidade em `backend/app/identity/`:
  - migração SQLite separada;
  - usuários e permissões;
  - proprietário imutável Eduardo;
  - senhas Argon2id e migração do SHA-256 legado somente no bootstrap;
  - sessões opacas, persistidas, revogáveis e protegidas por CSRF;
  - auditoria sem segredos;
  - revogação ao desativar usuário ou trocar senha.
- [x] Revisões de código e segurança do domínio corrigidas: timing de login, autorização obrigatória em `list_users`, corrida de bootstrap e sessões após troca de senha.
- [x] Camada HTTP inicial em `backend/app/access_control.py`.
- [x] Rotas globais `/api/auth/login`, `/api/auth/session` e `/api/auth/logout`.
- [x] Rotas `/api/admin/users` para listar, criar, atualizar e excluir usuários.
- [x] Proteção das APIs dos painéis DRE e Fluxo e das operações do Admin Banco.
- [x] Rate limit em memória por IP + usuário iniciado na camada HTTP.
- [x] Novos componentes frontend entregues:
  - `frontend/src/auth/`;
  - `frontend/src/components/AppSidebar.jsx`;
  - `frontend/src/components/AccessManagementPanel.jsx`;
  - `frontend/src/components/accessControlModel.js`;
  - `frontend/src/styles/access-control.css`.
- [x] Testes de modelo do frontend: 26 aprovados no trabalho delegado, com 100% de linhas e 87,25% de branches nesses modelos.

## Status final — Etapa 1 concluída

Verificação executada em 2026-08-27 nesta sessão.

| Verificação | Comando | Resultado |
| --- | --- | --- |
| Suíte backend | `backend/.venv/bin/pytest -q backend/tests` | 372 aprovados, 1 xfail, 1 falha pré-existente |
| Cobertura backend | `pytest --cov=backend/app --cov-fail-under=80` | **83,52%** — gate atingido |
| Lint backend | `ruff check backend/app backend/tests` | limpo |
| Formatação backend | `ruff format --check backend/app` | 58 arquivos já formatados |
| Auditoria backend | `pip-audit -r backend/requirements.txt` | nenhuma vulnerabilidade conhecida |
| Testes de modelo frontend | `npm test` | 29 aprovados |
| Build frontend | `npm run build` | sucesso |
| Auditoria frontend | `npm audit --omit=dev` | 0 vulnerabilidades |
| E2E Playwright | `npx playwright test` | 1 aprovado |

Cobertura dos módulos de identidade: `models.py` 100%, `repository.py` 96%, `passwords.py` 93%, `service.py` 90%.

### Falha pré-existente, fora do escopo

`backend/tests/test_dre_processamento.py::test_processamento_dre_gera_arquivo_e_log` falha ao comparar `xl/worksheets/sheet5.xml` byte a byte com o template: a saída perde a declaração `<?xml version="1.0" ...?>`. Reproduzido em worktree limpo no commit `1eb5104`, portanto **não é regressão do controle de acesso**. Continua em aberto como item separado do pipeline DRE.

## Entregas desta etapa

- Login global com sessões opacas, persistidas, revogáveis e CSRF.
- Senha temporária: o admin cria (ou redefine) a senha e o usuário é obrigado a trocá-la antes de ver qualquer painel.
  - `V2__add_temporary_password.sql` adiciona `must_change_password`.
  - `POST /api/auth/change-password` troca a senha e renova a sessão.
  - `require_permission`, `require_permissions` e `require_permission_with_csrf` retornam 403 enquanto a troca estiver pendente.
  - `session_payload` devolve `password_change_required: true` e `modules: []`, sem vazar painéis.
  - Redefinição pelo admin via `PATCH /api/admin/users/{id}` também reativa a obrigatoriedade.
  - Frontend: `PasswordChangeScreen` bloqueia a aplicação até a troca.
- Menu lateral (`AppSidebar`) substituindo as abas superiores, com drawer no mobile.
- Painel `AccessManagementPanel` para gestão de usuários e permissões.
- Remoção do login local do Admin Banco; a sessão passou a ser global.
- Rate limit de login por IP + usuário, com teste de regressão (429 na sexta tentativa, login válido zera o contador).
- Banco de identidade incluído no readiness check `/ready`.
- CORS restrito a `GET, POST, PATCH, DELETE, OPTIONS`.
- `.gitignore` cobrindo banco de identidade e artefatos de teste (`.coverage`, `frontend/test-results/`).

## Pendências e riscos conhecidos

- [ ] Falha pré-existente do template DRE (`sheet5.xml` sem declaração XML) — tratar no pipeline DRE.
- [ ] `data/aideal.db` continua versionado. Retirada segura do Git e migração para volume protegido seguem como bloqueador de produção.
- [ ] Em produção: habilitar HTTPS e `AIDEAL_ADMIN_COOKIE_SECURE=true`.
- [ ] Remover o caminho legado de bootstrap por variáveis de ambiente após validação em produção.
- [ ] Bundle do frontend em 780 kB (248 kB gzip). Avaliar code splitting.
- [ ] Painel Orçamento é Etapa 2. A permissão `orcamento.view` existe no schema, mas o módulo não aparece nesta entrega.

## Histórico do planejamento

### Ponto atual

- O conjunto backend focado passou em 71 testes; 3 testes antigos falharam porque o helper passou a autenticar automaticamente. Foi aplicado `client.cookies.clear()` nos três cenários que verificam acesso anônimo. Rodar novamente para confirmar.
- O frontend novo ainda precisa ser ligado ao `main.jsx`, `App.jsx` e `AdminPanel.jsx`.
- O rate limit ainda precisa de teste de regressão.
- A suíte completa, cobertura, lint, build e E2E ainda não foram executados após a integração final.

## Próximas tarefas, em ordem

### 1. Fechar backend GREEN

- [ ] Rodar os testes focados abaixo e corrigir qualquer regressão:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_identity_migrations.py \
  backend/tests/test_identity_passwords.py \
  backend/tests/test_identity_service.py \
  backend/tests/test_access_control_api.py \
  backend/tests/test_admin_auth.py \
  backend/tests/test_paineis_api.py \
  backend/tests/test_dashboard_resumo_api.py
```

- [ ] Adicionar teste de rate limit: após cinco credenciais inválidas, a sexta tentativa deve retornar 429; um login válido deve limpar o contador.
- [ ] Confirmar que `/api/auth/logout` exige CSRF e revoga a sessão no servidor.
- [ ] Confirmar que usuário sem `users.manage` recebe 403 em GET/POST/PATCH de usuários.
- [ ] Confirmar que campos de mass assignment (`is_system_owner`, `role`, `created_by`) recebem 422 devido a `extra="forbid"`.
- [ ] Adicionar o banco de identidade ao readiness check.
- [ ] Revisar CORS: permitir apenas métodos necessários, incluindo PATCH, e manter credenciais coerentes com a implantação de mesma origem.

### 2. Integrar frontend

- [ ] Envolver a aplicação com `AuthProvider` em `frontend/src/main.jsx`.
- [ ] Em `frontend/src/App.jsx`:
  - exibir `LoginScreen` quando não houver sessão;
  - substituir `WaveBar` por `AppSidebar`;
  - obter módulos e permissões de `useAuth()`;
  - selecionar somente uma view autorizada;
  - renderizar `AccessManagementPanel` para `usuarios`;
  - nunca renderizar Orçamento nesta etapa, mesmo que a permissão já exista no catálogo.
- [ ] Refatorar `frontend/src/components/AdminPanel.jsx` para remover login/logout local. A sessão passa a ser global; logout fica no menu lateral.
- [ ] Adicionar layout principal grid/flex para sidebar fixa no desktop e drawer no mobile.
- [ ] Corrigir a regra CSS do botão hambúrguer: o seletor atual usa irmão posterior, mas o botão aparece antes do `aside`.
- [ ] Validar foco, Escape, aria-current e teclado no menu mobile.

### 3. Testes de UI e E2E

- [ ] Adicionar testes de componente para `AuthContext`, `AppSidebar` e `AccessManagementPanel`.
- [ ] Cobrir owner protegido, erro de API, estado ocupado e fechamento do drawer no logout.
- [ ] Criar E2E Playwright dos fluxos críticos:
  1. Eduardo entra e vê DRE, Fluxo, Admin Banco e Controle de Acessos.
  2. Eduardo cria Ana apenas com DRE.
  3. Ana entra, vê somente DRE e recebe 403 ao chamar Fluxo e usuários diretamente.
  4. Eduardo desativa Ana; a sessão aberta de Ana perde acesso imediatamente.

### 4. Verificação final

- [ ] Backend: suíte completa, Ruff, type check existente, `pip-audit` e cobertura >= 80%.
- [ ] Frontend: testes, cobertura >= 80%, lint, build e `npm audit`.
- [ ] Inspecionar inventário de rotas para garantir que nenhuma rota financeira nova ficou pública por omissão.
- [ ] Rodar revisão final de código e segurança; corrigir achados HIGH/CRITICAL.
- [ ] Revisar `git diff` e `git status`; preservar alterações do usuário.
- [ ] Atualizar este handoff com resultados finais e comandos exatos.

## Observações de segurança e implantação

- `data/aideal.db` já estava versionado e com permissões amplas antes deste trabalho. Não reescrever histórico sem autorização, mas tratar a retirada segura do Git e a migração para volume protegido como bloqueador de produção.
- Em produção, habilitar HTTPS e `AIDEAL_ADMIN_COOKIE_SECURE=true`.
- O bootstrap atual aproveita temporariamente as variáveis legadas para criar Eduardo uma única vez. Após implantação e validação, planejar remoção desse caminho legado e usar procedimento operacional seguro.
- O painel Orçamento pertence à Etapa 2. A permissão `orcamento.view` já existe para evolução do schema, mas o módulo não deve aparecer nesta entrega.
