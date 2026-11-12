<?php
// إعدادات التشغيل داخل Docker: كل القيم من متغيرات البيئة (ملف .env في جذر المشروع).
define('DB_HOST', getenv('GM_DB_HOST') ?: 'monitor-db');
define('DB_NAME', getenv('GM_DB_NAME') ?: 'monitor');
define('DB_USER', getenv('GM_DB_USER') ?: 'monitor');
define('DB_PASS', (string)getenv('GM_DB_PASS'));
define('CRON_KEY', getenv('GM_CRON_KEY') ?: 'CHANGE_ME_TO_LONG_RANDOM_STRING');
define('SSH_KEY', '/var/lib/ghani-monitor/id_ed25519');   // على volume خاص خارج مجلد الويب
