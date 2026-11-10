#!/usr/bin/env bash
# تشغيل «سومر بريد» على نطاق فرعي، فوق سومر الشغّال.
# قبلها: سجل A للنطاق الفرعي (مثلاً mail.sumeriq.tech) يأشر على IP الخادم.
# الاستخدام (كـ root من مجلد المشروع): bash deploy/setup-mail.sh mail.sumeriq.tech you@email.com
set -euo pipefail
MDOMAIN="${1:?اكتب النطاق: bash deploy/setup-mail.sh mail.sumeriq.tech you@email.com}"
EMAIL="${2:?اكتب إيميلك لشهادة SSL}"
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.yml -f deploy/docker-compose.kvm1.yml -f deploy/docker-compose.mail.yml"

echo "==> 1/4 فحص DNS"
MYIP=$(curl -fsS https://api.ipify.org || true)
DNSIP=$(getent ahostsv4 "$MDOMAIN" | awk 'NR==1{print $1}')
if [ -n "$MYIP" ] && [ "$MYIP" != "$DNSIP" ]; then
  echo "!! $MDOMAIN يأشر على ($DNSIP) والخادم ($MYIP). سوِّ سجل A وانتظر شوية."; exit 1
fi

echo "==> 2/4 شهادة SSL (عبر nginx الشغّال)"
mkdir -p /var/www/certbot
if [ ! -d "/etc/letsencrypt/live/$MDOMAIN" ]; then
  certbot certonly --webroot -w /var/www/certbot -d "$MDOMAIN" -m "$EMAIL" --agree-tos -n
fi
install -d -m 700 /etc/sumer-certs-mail
cp -L "/etc/letsencrypt/live/$MDOMAIN/fullchain.pem" "/etc/letsencrypt/live/$MDOMAIN/privkey.pem" /etc/sumer-certs-mail/
chmod 600 /etc/sumer-certs-mail/*.pem
cat > /etc/letsencrypt/renewal-hooks/deploy/sumer-mail.sh <<HOOK
#!/bin/sh
cp -L /etc/letsencrypt/live/$MDOMAIN/fullchain.pem /etc/letsencrypt/live/$MDOMAIN/privkey.pem /etc/sumer-certs-mail/
cd $(pwd) && $COMPOSE restart nginx
HOOK
chmod +x /etc/letsencrypt/renewal-hooks/deploy/sumer-mail.sh

echo "==> 3/4 سر الجلسات"
grep -q '^SUMERMAIL_SECRET=' .env || echo "SUMERMAIL_SECRET=$(openssl rand -hex 32)" >> .env

echo "==> 4/4 بناء وتشغيل سومر بريد"
$COMPOSE up -d --build mail-api mail-web
$COMPOSE up -d --force-recreate nginx
echo
echo "✅ افتح: https://$MDOMAIN"
