# Test Run Report — 2026-04-02 (Atualizado)

Projeto: `/Users/gousero/Abiente Dev/ScriptPyAiDeal`

## Frameworks detectados
- `pytest` no backend (`backend/pyproject.toml`, `backend/tests/conftest.py`)
- Nenhuma suíte de teste detectada no frontend (`frontend/package.json` sem script `test`)

## Execução realizada
- Backend: `./.venv/bin/python -m pytest -q` (em `backend/`)
- Frontend: `npm run build` (sanidade de empacotamento)

## Resumo executivo
- Backend: sucesso com `119 passed`, `1 xfailed`, `0 failed`.
- Frontend: build de sanidade passou.
- Cobertura: não coletada (`pytest-cov` não instalado).

## Backend — `pytest`

### Resultado
- `suiteName`: `backend/pytest`
- `framework`: `pytest`
- `status`: `passed`
- `total`: `120`
- `passed`: `119`
- `failed`: `0`
- `skipped`: `0`
- `xfailed`: `1`
- `duration`: `28.94s`
- `coverage`: `não coletada`

### Correções validadas
- Validação cumulativa restaurada como padrão (jan..competência).
- Bloqueios de período cumulativo reativados (meses faltantes, mês acima, ano divergente, competência inválida).
- Tratamento robusto para entrada sem abas (sem `IndexError`).
- Persistência DRE ajustada para evitar colisão de hash em linhas repetidas legítimas no mesmo upload.

## Frontend — build de sanidade
- Comando: `npm run build`
- Resultado: sucesso
- Observação: não existe suíte de testes automatizada configurada no frontend.

## Cobertura
- Não coletada.
- Motivo: `pytest-cov` não está instalado na venv do backend.
