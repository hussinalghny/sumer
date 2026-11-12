<?php
/* GHANI Monitor Agent v2 — ارفعه باسم gm-agent.php في المجلد العام للموقع (public_html أو public) */
defined('GM_CF') || define('GM_CF', false); /*__GM_CF__*/

/* ===== وضع الحارس: عند تضمين الملف (require_once / auto_prepend_file) يسجّل الطلب ويطبّق الحظر والإغلاق ===== */
if (!isset($_SERVER['SCRIPT_FILENAME']) || realpath($_SERVER['SCRIPT_FILENAME']) !== __FILE__) {
    if (PHP_SAPI !== 'cli' && !defined('GM_SEEN')) {
        define('GM_SEEN', 1);
        (function () {
            $b = sys_get_temp_dir() . '/gm_' . md5(__FILE__);
            $ip = preg_replace('~[^0-9a-fA-F:.]~', '', (string)((GM_CF ? ($_SERVER['HTTP_CF_CONNECTING_IP'] ?? null) : null) ?? $_SERVER['REMOTE_ADDR'] ?? ''));
            $deny = '-';
            $st = @json_decode((string)@file_get_contents($b . '.state'), true);
            if ($st && !in_array($ip, $st['allow'] ?? [], true)) {
                $x = $st['block'][$ip] ?? null;
                if ($x !== null && ($x == 0 || $x > time())) $deny = 'B';
                elseif (!empty($st['lock'])) $deny = 'L';
            }
            if (@filesize($b . '.log') < 20971520) @file_put_contents($b . '.log', implode('|', [time(), $ip,
                preg_replace('~[^A-Z]~', '', (string)($_SERVER['REQUEST_METHOD'] ?? '')),
                str_replace(['|', "\n", "\r"], ['%7C', '', ''], substr((string)($_SERVER['REQUEST_URI'] ?? '/'), 0, 300)), $deny,
                str_replace(["\n", "\r"], '', substr((string)($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 100))]) . "\n", FILE_APPEND | LOCK_EX);
            if ($deny === 'B') { http_response_code(403); exit('403 Forbidden'); }
            if ($deny === 'L') { http_response_code(503); header('Retry-After: 900');
                exit('<!doctype html><meta charset="utf-8"><body style="font-family:sans-serif;text-align:center;padding:15vh 20px"><h2>الموقع تحت الصيانة مؤقتاً</h2><p>Site under maintenance</p>'); }
        })();
    }
    return;
}

/* ===== وضع الوكيل: طلبات موقّعة من نظام المراقبة فقط ===== */
const GM_SECRET = '__GM_SECRET__';
const GM_UP = 0; /*__GM_UP__*/
const GM_WANT = '~(\.(php\d?|phtml|pht|phar|inc|js|html?|cgi|pl|py|sh)(\.|$))|(^|/)(\.htaccess|\.user\.ini|php\.ini)$~i';

$ts = $_SERVER['HTTP_X_GM_TS'] ?? ''; $sig = $_SERVER['HTTP_X_GM_SIG'] ?? '';
$mode = $_GET['m'] ?? ''; $body = (string)file_get_contents('php://input');
if (strpos(GM_SECRET, '__') === 0 || !ctype_digit($ts) || abs(time() - (int)$ts) > 300
    || !hash_equals(hash_hmac('sha256', $ts . '|' . $mode . '|' . sha1($body), GM_SECRET), $sig)) {
    http_response_code(404); exit;
}
@set_time_limit(120); @ini_set('memory_limit', '256M');
$root = realpath(__DIR__ . str_repeat('/..', GM_UP));
$in = json_decode($body, true) ?: [];
$tmp = sys_get_temp_dir() . '/gm_' . md5(__FILE__);
$qdir = $root . '/.gm-quarantine';
$webdir = __DIR__; $selfFile = __FILE__; $up = GM_UP;
$self = str_replace('\\', '/', substr(__FILE__, strlen($root) + 1));
header('Content-Type: application/json'); ob_start('ob_gzhandler');

/*GM_CORE*/ /* من هنا: نفس الكود يُنفَّذ أيضاً عبر SSH بدون رفع أي ملف */

function gm_walk(string $root): Generator {
    $skip = '~(^|/)(node_modules|\.git|\.gm-quarantine|storage/framework|storage/logs|bootstrap/cache|wp-content/cache)(/|$)~';
    $len = strlen($root) + 1;
    $flt = new RecursiveCallbackFilterIterator(new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS), function ($f) use ($skip, $len) {
        return !$f->isDir() || !preg_match($skip, str_replace('\\', '/', substr($f->getPathname(), $len)));
    });
    foreach (new RecursiveIteratorIterator($flt, RecursiveIteratorIterator::LEAVES_ONLY, RecursiveIteratorIterator::CATCH_GET_CHILD) as $f)
        if ($f->isFile()) yield str_replace('\\', '/', substr($f->getPathname(), $len)) => $f;
}
function gm_manifest(string $root): array {
    $out = [];
    foreach (gm_walk($root) as $rel => $f) {
        if (!preg_match(GM_WANT, $rel)) continue;
        $out[$rel] = $f->getSize() <= 2097152 ? (string)@md5_file($f->getPathname()) : 'L' . $f->getSize() . '-' . $f->getMTime();
    }
    ksort($out, SORT_STRING);
    return $out;
}
function gm_in(string $root, string $p): ?string {
    $f = realpath($root . '/' . $p);
    return ($f && strpos($f, $root . DIRECTORY_SEPARATOR) === 0 && is_file($f)) ? $f : null;
}
function gm_match(string $src, string $rel): array {
    static $strong = [
        'eval على مدخلات أو كود مشفّر' => '~eval\s*\(\s*(base64_decode|gzinflate|gzuncompress|str_rot13|strrev|\$_(POST|GET|REQUEST|COOKIE))~i',
        'تنفيذ أوامر النظام من مدخلات المستخدم' => '~\b(system|shell_exec|passthru|exec|popen|proc_open|assert)\s*\(\s*\$_(POST|GET|REQUEST|COOKIE)~i',
        'توقيع Webshell معروف' => '~c99shell|r57shell|b374k|FilesMan|IndoXploit|alfa.?shell|WSO\s?\d\.\d|p0wny|weevely~i',
        'استدعاء دالة من مدخلات المستخدم' => '~\$_(POST|GET|REQUEST|COOKIE)\s*\[[^\]]+\]\s*\(\s*\$_(POST|GET|REQUEST|COOKIE)~',
        'تضمين ملف من مدخلات المستخدم' => '~\b(include|require)(_once)?\s*\(?\s*\$_(POST|GET|REQUEST|COOKIE)~i',
    ], $weak = [
        'فك تشفير مدخلات' => '~base64_decode\s*\(\s*\$_(POST|GET|REQUEST|COOKIE)~i',
        'دالة متغيرة من مدخلات' => '~\$_(POST|GET|REQUEST|COOKIE)\s*\[[^\]]+\]\s*\(~',
        'auto_prepend أو تنفيذ PHP بامتداد صور (طبيعي فقط إذا أنت ربطت الحارس)' => '~auto_prepend_file|Add(Handler|Type)[^\n]*php[^\n]*\.(jpe?g|png|gif|ico)~i',
        'نص مشفّر طويل جداً' => '~[A-Za-z0-9+/]{3000,}~',
        'تعتيم كود (hex/chr)' => '~\$\{?["\']\\\\x[0-9a-f]{2}|(chr\(\d+\)\s*\.\s*){4}~i',
        'create_function / assert على متغير' => '~create_function\s*\(|assert\s*\(\s*\$~i',
    ];
    $r = ['s' => [], 'w' => []];
    if (preg_match('~\.(jpe?g|png|gif|ico|bmp|webp)$~i', $rel)) { if (strpos($src, '<?php') !== false) $r['s'][] = 'كود PHP مخفي داخل ملف صورة'; return $r; }
    foreach ($strong as $n => $re) if (preg_match($re, $src)) $r['s'][] = $n;
    foreach ($weak as $n => $re) if (preg_match($re, $src)) $r['w'][] = $n;
    return $r;
}
function gm_perms(string $f): string { return substr(sprintf('%o', (int)@fileperms($f)), -4); }
function gm_out(array $a): void { echo json_encode(['ok' => 1] + $a, JSON_INVALID_UTF8_SUBSTITUTE); exit; }

switch ($mode) {
case 'sum': case 'full':
    $files = gm_manifest($root);
    gm_out(['sum' => md5(json_encode($files)), 'count' => count($files)] + ($mode === 'full' ? ['files' => $files] : []));

case 'inspect':
    $sus = [];
    foreach ($in as $p) {
        if ($p === $self || !($f = gm_in($root, (string)$p))) continue;
        $m = gm_match((string)@file_get_contents($f, false, null, 0, 1048576), $p);
        if ($m['s'] || $m['w']) $sus[$p] = $m;
    }
    gm_out(['sus' => $sus]);

case 'stats':
    $f = $tmp . '.log'; $t = $f . '.read';
    $tags = [
        'sqli' => '~union(\s|\+|/\*.*?\*/)+(all(\s|\+)+)?select|sleep\(\d|benchmark\(|information_schema|\'(\s|\+)*or(\s|\+)+[\'\d]|;(\s|\+)*drop(\s|\+)|extractvalue\(|updatexml\(~i',
        'lfi' => '~\.\./|\.\.\\\\|/etc/passwd|php://|file://|expect://|data://text|/proc/self~i',
        'xss' => '~<script|onerror\s*=|onload\s*=|javascript:|<svg[\s/]|<iframe~i',
        'rce' => '~[;|`]\s*(cat|ls|wget|curl|id|whoami|uname|nc)\b|\$\(|base64_decode\(|eval\(|system\(|phpinfo\(~i',
        'probe' => '~/\.env|/\.git/|/phpmyadmin|/adminer|/phpunit|eval-stdin|/\.aws|/\.ssh|/phpinfo|/wp-config\.php\.|\.(sql|bak|old)(\?|$)|/(shell|c99|r57|wso|alfa)\d*\.php|/cgi-bin/~i',
    ];
    $bots = '~sqlmap|nikto|nmap|masscan|wpscan|acunetix|nuclei|dirbuster|gobuster|ffuf|zgrab|hydra|nessus|openvas~i';
    $total = 0; $blocked = 0; $ips = []; $paths = []; $login = []; $atk = []; $hot = []; $rest = [];
    // طلبات نظام المراقبة نفسه لا تُحسب ولا تُصنَّف كهجوم
    $mon = preg_replace('~[^0-9a-fA-F:.]~', '', (string)((GM_CF ? ($_SERVER['HTTP_CF_CONNECTING_IP'] ?? null) : null) ?? $_SERVER['REMOTE_ADDR'] ?? ''));
    if (@rename($f, $t) || is_file($t)) {
        $fh = fopen($t, 'r');
        while ($fh && ($l = fgets($fh)) !== false) {
            $p = explode('|', rtrim($l, "\r\n"), 6);
            if (count($p) < 6) continue;
            [$when, $ip, $mth, $uri, $deny, $ua] = $p;
            if ($ip === $mon && strpos($ua, 'GhaniMonitor') !== false) continue;
            if ($deny === 'B') { $blocked++; continue; }
            $path = (string)strtok($uri, '?'); $dec = rawurldecode($uri); $tag = '';
            foreach ($tags as $n => $re) if (preg_match($re, $dec)) { $tag = $n; break; }
            if (!$tag && preg_match($bots, $ua)) $tag = 'scanner';
            $total++; $ips[$ip] = ($ips[$ip] ?? 0) + 1; $paths[$path] = ($paths[$path] ?? 0) + 1;
            if ($mth === 'POST' && preg_match('~login|signin|sign-in|auth|admin|xmlrpc|password~i', $path)) $login[$ip] = ($login[$ip] ?? 0) + 1;
            if ($tag) $atk[$ip][$tag] = ($atk[$ip][$tag] ?? 0) + 1;
            $row = [(int)$when, $ip, $mth, $uri, $ua, $tag];
            if ($tag || $mth !== 'GET') { if (count($hot) < 1500) $hot[] = $row; } elseif (count($rest) < 500) $rest[] = $row;
        }
        if ($fh) fclose($fh);
        @unlink($t);
    }
    arsort($ips); arsort($paths); arsort($login);
    uasort($atk, fn($a, $b) => array_sum($b) <=> array_sum($a));
    gm_out(['total' => $total, 'blocked' => $blocked, 'uniq' => count($ips), 'ips' => array_slice($ips, 0, 10, true),
        'paths' => array_slice($paths, 0, 10, true), 'login' => array_slice($login, 0, 5, true), 'atk' => array_slice($atk, 0, 20, true),
        'rows' => array_merge($hot, $rest), 'sh' => is_file($tmp . '.state') ? md5((string)file_get_contents($tmp . '.state')) : '']);

case 'setstate':
    if (!is_array(json_decode($body, true))) gm_out(['sh' => '']);
    file_put_contents($tmp . '.state', $body, LOCK_EX);
    gm_out(['sh' => md5($body)]);

case 'quarantine':
    if (!is_dir($qdir)) { @mkdir($qdir, 0700); @file_put_contents($qdir . '/.htaccess', "Require all denied\n"); @file_put_contents($qdir . '/index.html', ''); }
    $res = [];
    foreach ((array)($in['paths'] ?? []) as $p) {
        $f = gm_in($root, (string)$p); $r = ['path' => $p, 'ok' => 0];
        if ($f && $f !== $selfFile && is_dir($qdir)) {
            $q = bin2hex(random_bytes(8));
            $meta = ['path' => $p, 'perms' => gm_perms($f), 'mtime' => filemtime($f), 'ctime' => filectime($f), 'size' => filesize($f),
                     'md5' => md5_file($f), 'sha256' => hash_file('sha256', $f), 'at' => time()];
            if (@rename($f, "$qdir/$q.q")) { @chmod("$qdir/$q.q", 0400); file_put_contents("$qdir/$q.json", json_encode($meta)); $r = ['ok' => 1, 'q' => $q] + $meta; }
        }
        $res[] = $r;
    }
    gm_out(['res' => $res]);

case 'restore': case 'qdelete':
    $q = (string)($in['q'] ?? '');
    if (!preg_match('~^[a-f0-9]{16}$~', $q) || !is_file("$qdir/$q.q")) gm_out(['done' => 0]);
    if ($mode === 'qdelete') { @chmod("$qdir/$q.q", 0600); gm_out(['done' => (int)(@unlink("$qdir/$q.q") && (@unlink("$qdir/$q.json") || true))]); }
    $meta = json_decode((string)@file_get_contents("$qdir/$q.json"), true);
    $dest = $root . '/' . ($meta['path'] ?? ''); $dir = realpath(dirname($dest));
    if (!$meta || !$dir || strpos($dir . DIRECTORY_SEPARATOR, $root . DIRECTORY_SEPARATOR) !== 0 || file_exists($dest)) gm_out(['done' => 0]);
    $okk = @rename("$qdir/$q.q", $dest);
    if ($okk) { @chmod($dest, octdec($meta['perms'] ?: '0644')); @unlink("$qdir/$q.json"); }
    gm_out(['done' => (int)$okk]);

case 'get':
    $q = (string)($in['q'] ?? ''); $p = (string)($in['path'] ?? '');
    if ($q !== '') $f = preg_match('~^[a-f0-9]{16}$~', $q) && is_file("$qdir/$q.q") ? "$qdir/$q.q" : null;
    else $f = (preg_match(GM_WANT, $p) || preg_match('~\.(jpe?g|png|gif|ico|bmp|webp|txt)$~i', $p)) ? gm_in($root, $p) : null;
    if (!$f) gm_out(['found' => 0]);
    if ($q !== '') { $meta = json_decode((string)@file_get_contents("$qdir/$q.json"), true); $p = $meta['path'] ?? $p; @chmod($f, 0600); }
    $src = (string)@file_get_contents($f, false, null, 0, 204800);
    if ($q !== '') @chmod($f, 0400);
    gm_out(['found' => 1, 'path' => $p, 'size' => filesize($f), 'mtime' => filemtime($f), 'ctime' => filectime($f), 'perms' => gm_perms($f),
        'md5' => md5_file($f) ?: '', 'sha256' => hash_file('sha256', $f) ?: '', 'hits' => gm_match($src, $p), 'b64' => base64_encode($src)]);

case 'timeline':
    $since = time() - max(1, (int)($in['hours'] ?? 24)) * 3600; $out = [];
    foreach (gm_walk($root) as $rel => $f) if ($f->getCTime() >= $since) $out[] = [$rel, $f->getSize(), $f->getMTime(), $f->getCTime(), gm_perms($f->getPathname())];
    usort($out, fn($a, $b) => $b[3] <=> $a[3]);
    gm_out(['count' => count($out), 'files' => array_slice($out, 0, 400)]);

case 'scan':
    $skip = (int)($in['skip'] ?? 0); $i = 0; $n = 0; $hits = []; $t0 = microtime(true); $done = 1;
    foreach (gm_walk($root) as $rel => $f) {
        if ($i++ < $skip) continue;
        if ($n % 40 === 0 && microtime(true) - $t0 > 35) { $i--; $done = 0; break; }
        $img = preg_match('~\.(jpe?g|png|gif|ico|bmp|webp)$~i', $rel);
        if ($rel === $self || (!$img && !preg_match(GM_WANT, $rel)) || $f->getSize() > 2097152) continue;
        $n++;
        $m = gm_match((string)@file_get_contents($f->getPathname(), false, null, 0, $img ? 65536 : 1048576), $rel);
        if ($m['s'] || $m['w']) $hits[] = [$rel, $m['s'], $m['w']];
    }
    gm_out(['done' => $done, 'next' => $i, 'scanned' => $n, 'hits' => $hits]);

case 'audit':
    $fd = []; $add = function (string $sev, string $t, string $d) use (&$fd) { $fd[] = [$sev, $t, $d]; };
    $web = $webdir; $weblen = strlen($root) + 1; $webrel = trim(str_replace('\\', '/', substr($web, strlen($root))), '/');
    if (version_compare(PHP_VERSION, '8.2', '<')) $add('med', 'إصدار PHP قديم (' . PHP_VERSION . ')', 'لم يعد يستلم تحديثات أمنية. حدّث إلى إصدار مدعوم من لوحة الاستضافة.');
    if (filter_var(ini_get('display_errors'), FILTER_VALIDATE_BOOLEAN)) $add('med', 'display_errors مفعّل', 'رسائل الأخطاء تكشف مسارات وتفاصيل داخلية للزوار. عطّله في الإنتاج.');
    if (filter_var(ini_get('allow_url_include'), FILTER_VALIDATE_BOOLEAN)) $add('high', 'allow_url_include مفعّل', 'يسمح بتضمين كود من روابط خارجية (RFI). عطّله فوراً.');
    $dis = array_map('trim', explode(',', (string)ini_get('disable_functions')));
    $open = array_values(array_filter(['exec', 'shell_exec', 'system', 'passthru', 'proc_open', 'popen'], fn($x) => function_exists($x) && !in_array($x, $dis, true)));
    if ($open) $add('low', 'دوال تنفيذ أوامر النظام متاحة', implode(', ', $open) . ' — إذا الموقع لا يحتاجها عطّلها من disable_functions لتقليل ضرر أي Webshell.');
    if (is_dir($web . '/.git')) $add('high', 'مجلد ‎.git داخل المجلد العام', 'يمكن سحب كامل الكود المصدري منه. احذفه أو امنع الوصول إليه.');
    if (is_file($web . '/.env')) $add('high', 'ملف ‎.env داخل المجلد العام', 'انقله خارج المجلد العام أو امنع الوصول إليه.');
    if ($up === 0 && (is_file($web . '/artisan') || is_dir($web . '/vendor'))) $add('high', 'المشروع كله داخل المجلد العام', 'artisan/vendor ظاهرة داخل المجلد العام. اجعل الجذر يشير إلى مجلد public فقط.');
    foreach ([$root . '/.env', $web . '/.env'] as $e) if (is_file($e)) {
        $env = (string)@file_get_contents($e, false, null, 0, 20000);
        if (preg_match('~^\s*APP_DEBUG\s*=\s*"?true~mi', $env)) $add('high', 'APP_DEBUG=true في الإنتاج', 'صفحة الأخطاء تكشف متغيرات البيئة وكلمات السر. اجعلها false.');
        if (preg_match('~^\s*APP_ENV\s*=\s*"?local~mi', $env)) $add('low', 'APP_ENV=local', 'اجعلها production.');
        break;
    }
    $ww = []; $upl = []; $dump = []; $hid = []; $tools = []; $recent = 0; $nfiles = 0; $day2 = time() - 172800;
    foreach (gm_walk($root) as $rel => $f) {
        $nfiles++;
        if ($f->getCTime() >= $day2) $recent++;
        $isPhp = preg_match('~\.(php\d?|phtml|phar|pht)$~i', $rel);
        if (($f->getPerms() & 0002) && count($ww) < 15) $ww[] = $rel;
        if ($isPhp && preg_match('~(^|/)(uploads?|files|media|images|img|storage/app|avatars|attachments|documents)/~i', $rel) && count($upl) < 15) $upl[] = $rel;
        if ($isPhp && $rel !== $self && strpos(basename($rel), '.') === 0 && count($hid) < 15) $hid[] = $rel;
        if (preg_match('~(^|/)(adminer[^/]*\.php|tinyfilemanager\.php|filemanager\.php|phpinfo\.php|info\.php|eval-stdin\.php)$~i', $rel) && count($tools) < 15) $tools[] = $rel;
        $inweb = $webrel === '' ? $rel : (strpos($rel, $webrel . '/') === 0 ? substr($rel, strlen($webrel) + 1) : null);
        if ($inweb !== null && substr_count($inweb, '/') <= 1 && preg_match('~\.(sql|sql\.gz|bak|old|backup|tar|tar\.gz|tgz|zip|rar|7z)$~i', $rel) && count($dump) < 15) $dump[] = $rel;
    }
    if ($upl) $add('high', 'ملفات PHP داخل مجلدات الرفع', implode("\n", $upl) . "\nمجلدات الرفع لا يجب أن تحتوي كود تنفيذي — افحصها واعزل المشبوه وامنع تنفيذ PHP فيها.");
    if ($hid) $add('high', 'ملفات PHP مخفية (تبدأ بنقطة)', implode("\n", $hid));
    if ($dump) $add(preg_grep('~\.sql~i', $dump) ? 'high' : 'med', 'نسخ احتياطية/أرشيفات داخل المجلد العام', implode("\n", $dump) . "\nيمكن تنزيلها مباشرة بالرابط. انقلها خارج المجلد العام.");
    if ($tools) $add('med', 'أدوات إدارة/تشخيص خطرة موجودة', implode("\n", $tools) . "\nاحذفها بعد الاستخدام.");
    if ($ww) $add('med', 'ملفات قابلة للكتابة من الجميع (777/666)', implode("\n", $ww) . "\nغيّر الصلاحيات إلى 644 للملفات و755 للمجلدات.");
    gm_out(['findings' => $fd, 'info' => ['php' => PHP_VERSION, 'files' => $nfiles, 'recent48h' => $recent, 'server' => (string)($_SERVER['SERVER_SOFTWARE'] ?? '')]]);
}
echo json_encode(['ok' => 0]); exit;
