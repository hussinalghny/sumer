#!/usr/bin/env bash
# حصر لوحة GHANI Monitor بعناوين IP محددة.
#   bash deploy/monitor-acl.sh 1.2.3.4 5.6.7.8     السماح لهذه العناوين فقط (يقبل نطاقات مثل 1.2.3.0/24)
#   bash deploy/monitor-acl.sh off                 فتح اللوحة للجميع من جديد
#   bash deploy/monitor-acl.sh                     عرض الوضع الحالي
set -euo pipefail
cd "$(dirname "$0")/.."
ACL=/etc/sumer-monitor-acl/allow.conf
FILES="-f docker-compose.yml -f deploy/docker-compose.kvm1.yml"
[ -d /etc/sumer-certs-mail ] && FILES="$FILES -f deploy/docker-compose.mail.yml"
COMPOSE="docker compose $FILES -f deploy/docker-compose.monitor.yml"
mkdir -p /etc/sumer-monitor-acl

if [ $# -eq 0 ]; then
  if [ -s "$ACL" ]; then echo "اللوحة محصورة بـ:"; grep '^allow' "$ACL" | sed 's/allow /  /; s/;//'; else echo "اللوحة مفتوحة للجميع."; fi
  exit 0
fi
if [ "$1" = "off" ]; then
  rm -f "$ACL"
else
  : > "$ACL.new"
  for ip in "$@"; do
    echo "$ip" | grep -Eq '^[0-9a-fA-F:.]+(/[0-9]{1,3})?$' || { echo "!! عنوان غير صالح: $ip"; rm -f "$ACL.new"; exit 1; }
    echo "allow $ip;" >> "$ACL.new"
  done
  echo "deny all;" >> "$ACL.new"
  mv "$ACL.new" "$ACL"
fi
$COMPOSE up -d --force-recreate nginx >/dev/null
sleep 2
$COMPOSE exec -T nginx nginx -t >/dev/null 2>&1 || { echo "!! إعداد nginx غير صالح، أُلغي الحصر."; rm -f "$ACL"; $COMPOSE up -d --force-recreate nginx >/dev/null; exit 1; }
bash "$0"
