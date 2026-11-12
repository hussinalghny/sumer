<?php
// يُشغَّل كل 5 دقائق من Cron Jobs في hPanel
require __DIR__ . '/lib.php';
if (PHP_SAPI !== 'cli' && !hash_equals(CRON_KEY, (string)($_GET['key'] ?? ''))) { http_response_code(403); exit('forbidden'); }
echo run_checks() ? "ok\n" : "busy\n";
