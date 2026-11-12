# GHANI Monitor: PHP + Apache، مع عميل SSH لوضع الفحص بدون وكيل.
FROM php:8.3-apache
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client \
 && rm -rf /var/lib/apt/lists/* \
 && docker-php-ext-install pdo_mysql \
 && a2enmod remoteip \
 && printf 'RemoteIPHeader X-Real-IP\nRemoteIPInternalProxy 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16\nSetEnvIf X-Forwarded-Proto https HTTPS=on\nServerTokens Prod\nServerSignature Off\n' > /etc/apache2/conf-enabled/gm.conf \
 && install -d -o www-data -g www-data -m 700 /var/lib/ghani-monitor
COPY . /var/www/html/
# الإعدادات تُقرأ من متغيرات البيئة (لا أسرار داخل الصورة)
RUN mv /var/www/html/config.docker.php /var/www/html/config.php && rm -f /var/www/html/Dockerfile /var/www/html/config.sample.php /var/www/html/README.md
