#!/bin/bash
# ---------------------------------------------------------------------------
# One-time server setup: obtain initial Let's Encrypt certificate.
# Run this on the server BEFORE the first deploy, or when the cert doesn't
# exist yet. After this, the certbot container handles renewals automatically.
#
# Usage:  bash server_setup.sh <domain> [email]
#   domain  e.g. stg.mabitra.com
#   email   (optional) for Let's Encrypt notifications
# ---------------------------------------------------------------------------
set -e

DOMAIN="${1:?Usage: bash server_setup.sh <domain> [email]}"
EMAIL="${2:-}"
REMOTE_DIR="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd || echo /home/ubuntu/mabinogi)"

echo "==> Setting up Let's Encrypt for ${DOMAIN}..."

# 1. Start a temporary HTTP-only nginx for the ACME challenge
echo "==> Starting temporary nginx for ACME challenge..."
docker compose down nginx certbot 2>/dev/null || true

docker run -d --name mabi-certbot-init \
  -v mabinogi_certbot_www:/var/www/certbot \
  -v mabinogi_certbot_certs:/etc/letsencrypt \
  -p 80:80 \
  nginx:alpine \
  sh -c 'mkdir -p /var/www/certbot && nginx -g "daemon off;" -c /dev/stdin <<NGINX
events {}
http {
    server {
        listen 80;
        server_name ${DOMAIN};
        location /.well-known/acme-challenge/ { root /var/www/certbot; }
        location / { return 444; }
    }
}
NGINX'

echo "==> Requesting certificate..."
CERTBOT_ARGS="certonly --webroot -w /var/www/certbot -d ${DOMAIN} --agree-tos --non-interactive"
if [ -n "$EMAIL" ]; then
  CERTBOT_ARGS="$CERTBOT_ARGS --email $EMAIL"
else
  CERTBOT_ARGS="$CERTBOT_ARGS --register-unsafely-without-email"
fi

docker run --rm \
  -v mabinogi_certbot_www:/var/www/certbot \
  -v mabinogi_certbot_certs:/etc/letsencrypt \
  certbot/certbot $CERTBOT_ARGS

echo "==> Cleaning up temporary nginx..."
docker rm -f mabi-certbot-init

echo "==> Certificate obtained. You can now run deploy.sh."
echo "    Cert location (inside volume): /etc/letsencrypt/live/${DOMAIN}/"
