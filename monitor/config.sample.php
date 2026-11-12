<?php
// ===== إعدادات قاعدة البيانات (من hPanel > Databases) =====
const DB_HOST = 'localhost';
const DB_NAME = 'uXXXXXXX_monitor';
const DB_USER = 'uXXXXXXX_monitor';
const DB_PASS = 'CHANGE_ME';

// مفتاح سري طويل: يُستخدم لإنشاء كلمة مرور اللوحة أول مرة، ولتشغيل cron عبر الرابط
const CRON_KEY = 'CHANGE_ME_TO_LONG_RANDOM_STRING';

// (اختياري) مسار مفتاح SSH الخاص بالمراقب — يجب أن يكون خارج مجلد الويب. الافتراضي: ../.gm-keys/id_ed25519
// const SSH_KEY = '/var/lib/ghani-monitor/id_ed25519';
