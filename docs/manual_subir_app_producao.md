# Manual Curto para Subir a Aplicação

## Requisitos do servidor

- Linux com 2 vCPU, 4 GB RAM e 40 GB SSD.
- Python 3.11+ instalado.
- Node.js e npm instalados.
- Código do projeto copiado para o servidor.
- Banco inicial em `data/aideal.db`, se quiser preservar a base atual.

## Subir a aplicação

Na pasta raiz do projeto:

```bash
bash scripts/subir-producao.sh
```

O script prepara o ambiente, instala dependências, gera o frontend final e sobe a aplicação em:

```text
http://127.0.0.1:8000
```

## Verificar se está online

Em outro terminal:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

Resultado esperado:

```text
{"status":"ok"}
{"status":"ready", ...}
```

## Validar produção antes de usar

```bash
bash scripts/validate-prod.sh
```

Esse comando checa backend, segurança, build do frontend e disponibilidade.

## Parar a aplicação

No terminal onde o `subir-producao.sh` está rodando:

```text
Ctrl+C
```

## Porta diferente

Se precisar subir em outra porta local:

```bash
AIDEAL_PORT=8010 bash scripts/subir-producao.sh
```

## Observações

- A aplicação fica presa ao `localhost` por padrão.
- O frontend final é servido pelo backend; não use `npm run dev` em produção.
- O banco SQLite fica em `data/aideal.db`.
- Arquivos gerados ficam em `output/`.
