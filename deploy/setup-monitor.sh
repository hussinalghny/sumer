#!/usr/bin/env bash
# تشغيل GHANI Monitor على نطاق فرعي، فوق سومر الشغّال.
# قبلها: سجل A للنطاق الفرعي (مثلاً ghani.sumeriq.tech) يأشر على IP الخادم.
# الاستخدام (كـ root من مجلد المشروع): bash deploy/setup-monitor.sh ghani.sumeriq.tech you@email.com
set -euo pipefail
MDOMAIN="${1:?اكتب النطاق: bash deploy/setup-monitor.sh ghani.sumeriq.tech you@email.com}"
EMAIL="${2:?اكتب إيميلك لشهادة SSL}"
cd "$(dirname "$0")/.."
FILES="-f docker-compose.yml -f deploy/docker-compose.kvm1.yml"
# إذا «سومر بريد» مشغّل نُبقيه ضمن نفس التركيبة حتى لا يُحذف من nginx
[ -d /etc/sumer-certs-mail ] && FILES="$FILES -f deploy/docker-compose.mail.yml"
COMPOSE="docker compose $FILES -f deploy/docker-compose.monitor.yml"

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
install -d -m 700 /etc/sumer-certs-monitor
install -d -m 755 /etc/sumer-monitor-acl
cp -L "/etc/letsencrypt/live/$MDOMAIN/fullchain.pem" "/etc/letsencrypt/live/$MDOMAIN/privkey.pem" /etc/sumer-certs-monitor/
chmod 600 /etc/sumer-certs-monitor/*.pem
cat > /etc/letsencrypt/renewal-hooks/deploy/sumer-monitor.sh <<HOOK
#!/bin/sh
cp -L /etc/letsencrypt/live/$MDOMAIN/fullchain.pem /etc/letsencrypt/live/$MDOMAIN/privkey.pem /etc/sumer-certs-monitor/
cd $(pwd) && $COMPOSE restart nginx
HOOK
chmod +x /etc/letsencrypt/renewal-hooks/deploy/sumer-monitor.sh

echo "==> 3/4 الأسرار"
grep -q '^MONITOR_DB_PASSWORD=' .env || echo "MONITOR_DB_PASSWORD=$(openssl rand -hex 24)" >> .env
grep -q '^MONITOR_CRON_KEY=' .env || echo "MONITOR_CRON_KEY=$(openssl rand -hex 24)" >> .env

echo "==> 4/4 بناء وتشغيل المراقب"
$COMPOSE up -d --build monitor-db monitor monitor-cron
$COMPOSE up -d --force-recreate nginx
echo
echo "✅ افتح: https://$MDOMAIN"
echo "   مفتاح الإعداد الأول (CRON_KEY): $(grep '^MONITOR_CRON_KEY=' .env | cut -d= -f2)"
echo "   بعدها احصر اللوحة بعنوانك: bash deploy/monitor-acl.sh YOUR_IP"
