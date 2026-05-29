# Manual Curto para Subir a Aplicação

## Requisitos do servidor

- Linux com 2 vCPU, 4 GB RAM e 40 GB SSD.
- Acesso à internet para baixar pacotes Python/npm.
- Usuário com `sudo` na primeira execução, caso Python 3.11+, `python3-venv`, Node.js ou npm ainda não estejam instalados.
- Código do projeto copiado para o servidor.
- Banco inicial em `data/aideal.db`, se quiser preservar a base atual.

## Subir a aplicação

Na pasta raiz do projeto:

```bash
bash scripts/subir-producao.sh
```

O script prepara o ambiente, instala dependências, gera o frontend final e sobe a aplicação em todas as interfaces de rede:

```text
http://0.0.0.0:8000
```

Para acessar de outro computador na mesma rede, use o IP da máquina que está rodando o app, por exemplo `http://192.168.1.50:8000`.

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

- A aplicação fica disponível na rede local por padrão (`0.0.0.0`).
- O frontend final é servido pelo backend; não use `npm run dev` em produção.
- O script instala as dependências do frontend com as devDependencies necessárias para build (`Vite`, `Next`, plugins etc. quando estiverem no `package.json`).
- Se Node.js estiver ausente ou incompatível em servidores Debian/Ubuntu, o script tenta instalar Node.js 22 LTS via NodeSource.
- Para restringir novamente ao próprio servidor, rode com `AIDEAL_HOST=127.0.0.1 bash scripts/subir-producao.sh`.
- Se outro dispositivo da rede não abrir, libere a porta `8000` no firewall do servidor.
- O banco SQLite fica em `data/aideal.db`.
- Arquivos gerados ficam em `output/`.
