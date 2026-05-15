#!/usr/bin/env bash
set -euo pipefail

# Load .env
if [ ! -f .env ]; then
  echo "ERRO: Arquivo .env não encontrado. Copie .env.example para .env e preencha."
  exit 1
fi
export $(grep -v '^#' .env | xargs)

EVOLUTION_URL="${EVOLUTION_API_URL:-http://localhost:8080}"
INSTANCE="${EVOLUTION_INSTANCE:-whatsapp-bot}"
BOT_URL="${BOT_WEBHOOK_URL:-http://localhost:3000}"

echo "==> Aguardando Evolution API iniciar..."
for i in $(seq 1 30); do
  if curl -sf "$EVOLUTION_URL/" > /dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "==> Criando instância '$INSTANCE'..."
curl -sf -X POST "$EVOLUTION_URL/instance/create" \
  -H "apikey: $EVOLUTION_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"instanceName\": \"$INSTANCE\", \"integration\": \"WHATSAPP-BAILEYS\"}" || true

echo ""
echo "==> Configurando webhook para $BOT_URL/webhook ..."
curl -sf -X POST "$EVOLUTION_URL/webhook/set/$INSTANCE" \
  -H "apikey: $EVOLUTION_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"url\": \"$BOT_URL/webhook\",
    \"webhook_by_events\": false,
    \"webhook_base64\": true,
    \"events\": [\"MESSAGES_UPSERT\"]
  }" || true

echo ""
echo "==> Gerando QR Code para conexão..."
curl -sf "$EVOLUTION_URL/instance/connect/$INSTANCE" \
  -H "apikey: $EVOLUTION_API_KEY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
qr = data.get('qrcode', {})
print()
print('Escaneie o QR Code abaixo com seu WhatsApp:')
print()
print(qr.get('qrcode', 'QR code não disponível — acesse http://localhost:8080 no navegador'))
"

echo ""
echo "==> Setup concluído! O bot estará pronto após escanear o QR Code."
