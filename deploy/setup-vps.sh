#!/usr/bin/env bash
# تنصيب سومر على VPS جديد (Ubuntu 22.04/24.04) — مثل Hostinger KVM 1.
# الاستخدام (كـ root، من داخل مجلد sumer-engine):
#   bash deploy/setup-vps.sh search.example.iq admin@example.iq
set -euo pipefail

DOMAIN="${1:?اكتب الدومين: bash deploy/setup-vps.sh search.example.iq admin@example.iq}"
EMAIL="${2:?اكتب إيميل الأدمن (يُستخدم لشهادة SSL ولحساب لوحة التحكم)}"
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.yml -f deploy/docker-compose.kvm1.yml"

echo "==> 1/7 تحديث النظام وتنصيب الأدوات"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl ufw certbot openssl dnsutils

echo "==> 2/7 ذاكرة Swap (2GB) حتى ما يوكف البناء على 4GB"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> 3/7 تنصيب Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

echo "==> 4/7 الجدار الناري: SSH و 80 و 443 فقط"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "==> 5/7 ملف الأسرار .env"
if [ ! -f .env ]; then
  cat > .env <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 24)
SUMER_APP_SECRET=$(openssl rand -hex 32)
SUMER_BACKUP_KEY=$(openssl rand -hex 32)
SUMER_COOKIE_SECURE=1
SUMER_DOMAIN=${DOMAIN}
EOF
  chmod 600 .env
  echo "   انعمل .env بأسرار عشوائية. انسخ SUMER_BACKUP_KEY لمكان آمن خارج الخادم!"
fi

echo "==> 6/7 شهادة SSL من Let's Encrypt"
MYIP=$(curl -fsS https://api.ipify.org || true)
DNSIP=$(dig +short "$DOMAIN" A | tail -1)
if [ -n "$MYIP" ] && [ "$MYIP" != "$DNSIP" ]; then
  echo "!! الدومين $DOMAIN يأشر على ($DNSIP) بس عنوان الخادم ($MYIP)."
  echo "!! سوِّ سجل A للدومين على $MYIP وانتظر شوية، وبعدين أعد تشغيل السكربت."
  exit 1
fi
mkdir -p /var/www/certbot
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
  certbot certonly --standalone -d "$DOMAIN" -m "$EMAIL" --agree-tos -n
fi
# التجديد التلقائي: certbot يجدد عبر مجلد التحدي، وبعدها نعيد تحميل nginx
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/sumer-nginx.sh <<EOF
#!/bin/sh
cd $(pwd) && $COMPOSE up -d --force-recreate nginx
EOF
chmod +x /etc/letsencrypt/renewal-hooks/deploy/sumer-nginx.sh
sed -i "s|^authenticator.*|authenticator = webroot\nwebroot_path = /var/www/certbot,|" "/etc/letsencrypt/renewal/$DOMAIN.conf"
grep -q '^webroot_path' "/etc/letsencrypt/renewal/$DOMAIN.conf" || \
  printf '[[webroot_map]]\n%s = /var/www/certbot\n' "$DOMAIN" >> "/etc/letsencrypt/renewal/$DOMAIN.conf"

echo "==> 7/7 بناء وتشغيل سومر (أول مرة ياخذ 10-20 دقيقة)"
$COMPOSE up -d --build

echo
echo "==> إنشاء حساب المدير الأول ($EMAIL)"
$COMPOSE run --rm api python -m sumer create-admin --email "$EMAIL" --name "Super Admin" --role super_admin

echo
echo "✅ خلص. افتح: https://$DOMAIN  ولوحة التحكم: https://$DOMAIN/admin"
echo "   فعّل التحقق بخطوتين من صفحة الحساب أول ما تدخل."
