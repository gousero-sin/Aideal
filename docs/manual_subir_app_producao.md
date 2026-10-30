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

O script prepara o ambiente, instala dependências, gera o frontend final e sobe a aplicação em todas as interfaces de rede do servidor. Os usuários acessam pelo nome, não pelo IP:

```text
http://goflowaideal.local (porta 80) ou http://goflowaideal.local:8000
```

O nome `goflowaideal` precisa resolver para o servidor em cada computador da rede; veja a seção abaixo.

## Endereço de acesso: goflowaideal

Escolha **uma** forma de fazer o nome `goflowaideal` apontar para o servidor:

1. **Registro DNS no roteador.** No painel do roteador ou do servidor DNS da rede, crie um registro `goflowaideal` apontando para o IP do servidor e reserve esse IP no DHCP para ele não mudar. Todos os computadores passam a abrir `http://goflowaideal:8000` sem configuração local.
2. **mDNS/avahi (adotado no servidor da AIDEAL).** No servidor, defina o hostname e instale o avahi:

   ```bash
   sudo hostnamectl set-hostname goflowaideal
   sudo apt-get install -y avahi-daemon
   ```

   O endereço passa a ser `http://goflowaideal.local:8000` (Windows 10+ e macOS resolvem `.local` nativamente).

   Para dispensar o `:8000`, o servidor redireciona a porta 80 para a 8000 no firewall (`iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-ports 8000`), reaplicado no boot pela unidade `aideal-porta80.service`. Nesse caso use `AIDEAL_PUBLIC_URL=http://goflowaideal.local` no `.env`.
3. **Arquivo hosts em cada cliente.** Acrescente a linha `<IP_do_servidor> goflowaideal` em `C:\Windows\System32\drivers\etc\hosts` (Windows) ou `/etc/hosts` (Linux/macOS). Precisa ser repetido em cada máquina e atualizado se o IP mudar.

A variável `AIDEAL_PUBLIC_URL` define o endereço exibido ao subir o app e incluído nas origens CORS permitidas. O padrão é `http://goflowaideal.local:<AIDEAL_PORT>`; mude apenas se usar outro nome:

```bash
AIDEAL_PUBLIC_URL=http://goflowaideal.local:8000 bash scripts/subir-producao.sh
```

O app continua sem HTTPS: o endereço é `http://`, nunca `https://`.

**Sessões abertas pelo IP exigem novo login.** O cookie de sessão fica preso ao endereço exato digitado no navegador; quem estava logado por `http://<IP>:8000` precisa entrar de novo em `http://goflowaideal.local`. Atualize também favoritos e atalhos.

## Configurar Admin Banco

Antes de subir em produção, configure a credencial administrativa fora do repositório:

```bash
export AIDEAL_ADMIN_USERNAME="Eduardo"
export AIDEAL_ADMIN_PASSWORD="<senha_admin>"
export AIDEAL_ADMIN_SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

Se preferir não expor a senha em variável direta, use `AIDEAL_ADMIN_PASSWORD_HASH` no formato `sha256:<hash_hex>` e deixe `AIDEAL_ADMIN_PASSWORD` vazio.

## Verificar se está online

Em outro terminal, no próprio servidor:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

De um computador da rede, confirme também que o nome resolve:

```bash
curl http://goflowaideal.local:8000/health
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

O endereço de acesso acompanha a porta: `http://goflowaideal.local:8010`.

## Observações

- A aplicação escuta em todas as interfaces do servidor por padrão e é acessada na rede por `http://goflowaideal.local:8000`.
- O frontend final é servido pelo backend; não use `npm run dev` em produção.
- O script instala as dependências do frontend com as devDependencies necessárias para build (`Vite`, `Next`, plugins etc. quando estiverem no `package.json`).
- Se Node.js estiver ausente ou incompatível em servidores Debian/Ubuntu, o script tenta instalar Node.js 22 LTS via NodeSource.
- Para restringir novamente ao próprio servidor, rode com `AIDEAL_HOST=127.0.0.1 bash scripts/subir-producao.sh`.
- Se outro dispositivo da rede não abrir, libere a porta `8000` no firewall do servidor.
- O banco SQLite fica em `data/aideal.db`.
- Arquivos gerados ficam em `output/`.
