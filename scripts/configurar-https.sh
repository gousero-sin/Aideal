#!/usr/bin/env bash
# AIDEAL GoFlowOS - HTTPS na rede local com Caddy e CA interna.
#
# Uso (no servidor, com senha de sudo):
#   sudo bash scripts/configurar-https.sh
#
# O Caddy escuta só na 443 e repassa para o app na 8000. A porta 80 continua
# com o redirecionamento iptables do serviço aideal-porta80, então o acesso
# por http:// segue funcionando enquanto a CA não estiver instalada em todos
# os computadores. Nomes .local não recebem certificado público: o Caddy emite
# o certificado com uma CA própria, exportada ao final para instalar nos
# clientes. O script é idempotente.

set -euo pipefail

HOST_PUBLICO="${AIDEAL_HTTPS_HOST:-goflowaideal.local}"
IP_LAN="${AIDEAL_HTTPS_IP:-$(hostname -I | awk '{print $1}')}"
UPSTREAM="${AIDEAL_UPSTREAM:-127.0.0.1:8000}"
DONO="${SUDO_USER:-sistema}"
CADDYFILE="/etc/caddy/Caddyfile"
CA_ORIGEM="/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt"
CA_DESTINO_DIR="/home/${DONO}/Aideal-ca"
CA_DESTINO="${CA_DESTINO_DIR}/goflowaideal-ca.crt"

log() { printf '%s\n' "$*"; }
die() { printf 'Erro: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "rode com sudo: sudo bash $0"
[ -n "$IP_LAN" ] || die "não foi possível descobrir o IP da rede local"

log "[1/5] Instalando Caddy..."
if ! command -v caddy >/dev/null 2>&1; then
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y caddy
fi
log "  $(caddy version)"

log "[2/5] Escrevendo ${CADDYFILE} (${HOST_PUBLICO}, ${IP_LAN} -> ${UPSTREAM})..."
NOVO_CADDYFILE="$(mktemp)"
cat > "$NOVO_CADDYFILE" <<EOF
{
	# A porta 80 é do redirecionamento iptables para o app (aideal-porta80).
	auto_https disable_redirects
	# A CA é distribuída manualmente aos clientes; não mexer no trust do servidor.
	skip_install_trust
}

https://${HOST_PUBLICO}, https://${IP_LAN} {
	tls internal
	encode gzip
	reverse_proxy ${UPSTREAM}
}
EOF
caddy validate --config "$NOVO_CADDYFILE" --adapter caddyfile >/dev/null
if [ -f "$CADDYFILE" ] && ! cmp -s "$NOVO_CADDYFILE" "$CADDYFILE"; then
    cp "$CADDYFILE" "${CADDYFILE}.bak-$(date +%Y%m%d-%H%M%S)"
fi
install -m 0644 "$NOVO_CADDYFILE" "$CADDYFILE"
rm -f "$NOVO_CADDYFILE"

log "[3/5] Ativando o serviço caddy..."
systemctl enable caddy >/dev/null 2>&1
systemctl restart caddy

log "[4/5] Aguardando a CA interna..."
for _ in $(seq 1 30); do
    [ -s "$CA_ORIGEM" ] && break
    sleep 1
done
[ -s "$CA_ORIGEM" ] || die "CA não encontrada em ${CA_ORIGEM}; veja: journalctl -u caddy -n 50"

log "[5/5] Exportando a CA para ${CA_DESTINO}..."
install -d -m 0755 -o "$DONO" -g "$DONO" "$CA_DESTINO_DIR"
install -m 0644 -o "$DONO" -g "$DONO" "$CA_ORIGEM" "$CA_DESTINO"

for _ in $(seq 1 20); do
    curl -sk -o /dev/null -m 5 --resolve "${HOST_PUBLICO}:443:127.0.0.1" \
        "https://${HOST_PUBLICO}/ready" && break
    sleep 1
done
CODIGO="$(curl -s -o /dev/null -m 5 -w '%{http_code}' --cacert "$CA_DESTINO" \
    --resolve "${HOST_PUBLICO}:443:127.0.0.1" "https://${HOST_PUBLICO}/ready" || true)"

log ""
log "HTTPS: https://${HOST_PUBLICO} e https://${IP_LAN} (ready=${CODIGO})"
log "CA para instalar nos clientes: ${CA_DESTINO}"
openssl x509 -in "$CA_DESTINO" -noout -subject -enddate -fingerprint -sha256
