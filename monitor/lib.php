<?php
require __DIR__ . '/config.php';
date_default_timezone_set('Asia/Baghdad');

const GM_TYPES = [
    'down'     => ['🔴', 'الموقع متوقف', 'down'],
    'files'    => ['🚨', 'تغيير في ملفات الموقع', 'danger'],
    'malware'  => ['☠️', 'كود خبيث (الفحص العميق)', 'danger'],
    'deface'   => ['🚨', 'اشتباه تشويه الصفحة (Defacement)', 'danger'],
    'redirect' => ['🚨', 'تحويل مشبوه لنطاق آخر', 'danger'],
    'scripts'  => ['🚨', 'سكربت/iframe خارجي جديد بالصفحة', 'danger'],
    'agent'    => ['🚨', 'الوكيل لا يستجيب', 'danger'],
    'dns'      => ['🚨', 'تغيّر خوادم DNS للنطاق', 'danger'],
    'attack'   => ['🎯', 'محاولات هجوم على الموقع', 'danger'],
    'flood'    => ['🌊', 'ارتفاع غير طبيعي بعدد الطلبات', 'danger'],
    'brute'    => ['🔑', 'محاولات دخول متكررة (Brute force)', 'danger'],
    'ipflood'  => ['🌊', 'IP واحد يرسل طلبات كثيرة', 'warn'],
    'vuln'     => ['🧱', 'ثغرة أو إعداد خطير', 'warn'],
    'title'    => ['⚠️', 'تغيّر عنوان الصفحة', 'warn'],
    'keyword'  => ['⚠️', 'الكلمة المتوقعة غير موجودة', 'warn'],
    'ssl'      => ['⚠️', 'شهادة SSL', 'warn'],
];
const GM_TAGS = ['sqli' => 'SQL Injection', 'lfi' => 'LFI / Path Traversal', 'xss' => 'XSS', 'rce' => 'RCE / Command Injection', 'probe' => 'بحث عن ملفات حساسة', 'scanner' => 'أداة فحص آلية'];

/* ================= أساسيات ================= */
function db(): PDO {
    static $p;
    if (!$p) $p = new PDO('mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4', DB_USER, DB_PASS,
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
    return $p;
}
function q(string $sql, array $a = []): PDOStatement { $st = db()->prepare($sql); $st->execute($a); return $st; }
function now(): string { return date('Y-m-d H:i:s'); }
function ago(int $secs): string { return date('Y-m-d H:i:s', time() - $secs); }
function h($s): string { return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }

function migrate(): void {
    db()->exec("CREATE TABLE IF NOT EXISTS gm_settings (k VARCHAR(50) PRIMARY KEY, v TEXT) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    if ((int)setting('schema', 0) >= 5) return;
    $try = function (string $sql) { try { db()->exec($sql); } catch (Throwable $e) {} };
    db()->exec("CREATE TABLE IF NOT EXISTS gm_sites (
        id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(120) NOT NULL, url VARCHAR(255) NOT NULL,
        keyword VARCHAR(120) NOT NULL DEFAULT '', deface_check TINYINT NOT NULL DEFAULT 1,
        agent_url VARCHAR(255) NULL, secret VARCHAR(64) NOT NULL, root_up TINYINT NOT NULL DEFAULT 0,
        http_code INT NULL, resp_ms INT NULL, fail_count INT NOT NULL DEFAULT 0,
        title_base VARCHAR(255) NULL, hosts_base TEXT NULL, ssl_expires DATETIME NULL, ssl_checked_at DATETIME NULL,
        agent_ok TINYINT NULL, agent_fail INT NOT NULL DEFAULT 0, files_count INT NULL,
        files_sum_base CHAR(32) NULL, files_sum_last CHAR(32) NULL, manifest MEDIUMTEXT NULL, files_diff MEDIUMTEXT NULL,
        last_check DATETIME NULL, created_at DATETIME NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    db()->exec("CREATE TABLE IF NOT EXISTS gm_issues (
        id INT AUTO_INCREMENT PRIMARY KEY, site_id INT NOT NULL, type VARCHAR(20) NOT NULL, message TEXT NOT NULL,
        opened_at DATETIME NOT NULL, closed_at DATETIME NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    db()->exec("CREATE TABLE IF NOT EXISTS gm_traffic (site_id INT NOT NULL, at DATETIME NOT NULL, total INT NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    foreach (['traffic_at DATETIME NULL', 'traffic_last TEXT NULL', 'cf TINYINT NOT NULL DEFAULT 0', 'lockdown TINYINT NOT NULL DEFAULT 0',
              'state_hash CHAR(32) NULL', 'score INT NULL', 'audit MEDIUMTEXT NULL', 'audit_at DATETIME NULL', 'scan MEDIUMTEXT NULL',
              'scan_at DATETIME NULL', 'scan_ignore TEXT NULL', 'dns_base TEXT NULL', 'ssh_host VARCHAR(190) NULL',
              'ssh_port INT NOT NULL DEFAULT 22', 'ssh_user VARCHAR(64) NULL', 'ssh_path VARCHAR(500) NULL', 'files_at DATETIME NULL'] as $c) $try("ALTER TABLE gm_sites ADD $c");
    db()->exec("CREATE TABLE IF NOT EXISTS gm_filelog (id INT AUTO_INCREMENT PRIMARY KEY, site_id INT NOT NULL, at DATETIME NOT NULL,
        path VARCHAR(500) NOT NULL, chg VARCHAR(10) NOT NULL, sus TEXT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    db()->exec("CREATE TABLE IF NOT EXISTS gm_requests (id INT AUTO_INCREMENT PRIMARY KEY, site_id INT NOT NULL, at DATETIME NOT NULL,
        ip VARCHAR(45) NOT NULL, method VARCHAR(8) NOT NULL, path VARCHAR(300) NOT NULL, ua VARCHAR(120) NOT NULL, tag VARCHAR(12) NOT NULL DEFAULT '') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    db()->exec("CREATE TABLE IF NOT EXISTS gm_blocks (id INT AUTO_INCREMENT PRIMARY KEY, site_id INT NOT NULL, ip VARCHAR(45) NOT NULL,
        reason VARCHAR(255) NOT NULL, actor VARCHAR(10) NOT NULL, at DATETIME NOT NULL, expires DATETIME NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    db()->exec("CREATE TABLE IF NOT EXISTS gm_quarantine (id INT AUTO_INCREMENT PRIMARY KEY, site_id INT NOT NULL, path VARCHAR(500) NOT NULL,
        qname CHAR(16) NOT NULL, md5 CHAR(32) NOT NULL, sha256 CHAR(64) NOT NULL, size INT NOT NULL, mtime DATETIME NULL, at DATETIME NOT NULL,
        reason VARCHAR(255) NOT NULL, actor VARCHAR(10) NOT NULL, state VARCHAR(10) NOT NULL DEFAULT 'held') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    db()->exec("CREATE TABLE IF NOT EXISTS gm_actions (id INT AUTO_INCREMENT PRIMARY KEY, site_id INT NOT NULL, at DATETIME NOT NULL,
        actor VARCHAR(10) NOT NULL, action VARCHAR(30) NOT NULL, detail TEXT NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    foreach (['gm_i1 ON gm_issues (site_id, closed_at)', 'gm_t1 ON gm_traffic (site_id, at)', 'gm_f1 ON gm_filelog (site_id, at)',
              'gm_r1 ON gm_requests (ip)', 'gm_r2 ON gm_requests (site_id, at)', 'gm_r3 ON gm_requests (at)'] as $i) $try("CREATE INDEX $i");
    set_setting('schema', '5');
}
function setting(string $k, $def = null) {
    $v = q('SELECT v FROM gm_settings WHERE k=?', [$k])->fetchColumn();
    return $v === false ? $def : $v;
}
function set_setting(string $k, string $v): void {
    q('INSERT INTO gm_settings (k,v) VALUES (?,?) ON DUPLICATE KEY UPDATE v=VALUES(v)', [$k, $v]);
}
function upd(int $id, array $f): void {
    $set = implode(',', array_map(fn($k) => "$k=?", array_keys($f)));
    q("UPDATE gm_sites SET $set WHERE id=?", [...array_values($f), $id]);
}
function site(int $id) { return q('SELECT * FROM gm_sites WHERE id=?', [$id])->fetch(); }
function act_log(int $sid, string $actor, string $action, string $detail): void {
    q('INSERT INTO gm_actions (site_id,at,actor,action,detail) VALUES (?,?,?,?,?)', [$sid, now(), $actor, $action, $detail]);
}
function jenc($v): string { return json_encode($v, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE); }

/* ================= HTTP والوكيل ================= */
function http_multi(array $reqs, int $timeout = 20): array {
    $mh = curl_multi_init(); $hs = []; $out = [];
    foreach ($reqs as $k => $r) {
        $c = curl_init($r['url']);
        curl_setopt_array($c, [
            CURLOPT_RETURNTRANSFER => true, CURLOPT_FOLLOWLOCATION => empty($r['nofollow']), CURLOPT_MAXREDIRS => 5,
            CURLOPT_CONNECTTIMEOUT => 10, CURLOPT_TIMEOUT => $r['timeout'] ?? $timeout, CURLOPT_ENCODING => '',
            CURLOPT_USERAGENT => 'Mozilla/5.0 (compatible; GhaniMonitor/2.0)', CURLOPT_HTTPHEADER => $r['headers'] ?? [],
            CURLOPT_HEADER => !empty($r['hdr']),
        ]);
        if (isset($r['range'])) curl_setopt($c, CURLOPT_RANGE, $r['range']);
        if (isset($r['post'])) { curl_setopt($c, CURLOPT_POST, true); curl_setopt($c, CURLOPT_POSTFIELDS, $r['post']); }
        curl_multi_add_handle($mh, $c); $hs[$k] = $c;
    }
    do { $st = curl_multi_exec($mh, $run); if ($run) curl_multi_select($mh, 1.0); } while ($run && $st === CURLM_OK);
    foreach ($hs as $k => $c) {
        $raw = (string)curl_multi_getcontent($c); $hd = '';
        if (!empty($reqs[$k]['hdr'])) { $n = (int)curl_getinfo($c, CURLINFO_HEADER_SIZE); $hd = substr($raw, 0, $n); $raw = (string)substr($raw, $n); }
        $out[$k] = ['code' => (int)curl_getinfo($c, CURLINFO_HTTP_CODE), 'body' => $raw, 'hdr' => $hd,
            'ms' => (int)round(curl_getinfo($c, CURLINFO_TOTAL_TIME) * 1000),
            'final' => (string)curl_getinfo($c, CURLINFO_EFFECTIVE_URL), 'err' => curl_error($c)];
        curl_multi_remove_handle($mh, $c); curl_close($c);
    }
    curl_multi_close($mh);
    return $out;
}
/* مفتاح التوقيع: الخاص يبقى هنا، والعام يُزرع داخل ملف الوكيل. اختراق أي موقع لا يكشف شيئاً عن بقية المواقع. */
function gm_keys(): array {
    static $k;
    if ($k) return $k;
    $priv = setting('agent_priv'); $pub = setting('agent_pub');
    if (!$priv || !$pub) {
        $res = openssl_pkey_new(['private_key_bits' => 2048, 'private_key_type' => OPENSSL_KEYTYPE_RSA]);
        if (!$res) throw new RuntimeException('تعذر توليد مفتاح التوقيع (OpenSSL)');
        openssl_pkey_export($res, $priv); $pub = openssl_pkey_get_details($res)['key'];
        set_setting('agent_priv', $priv); set_setting('agent_pub', $pub);
    }
    return $k = [$priv, $pub];
}
function agent_code(): string { return strtr((string)file_get_contents(__DIR__ . '/agent.tpl.php'), ['__GM_PUBKEY__' => trim(gm_keys()[1])]); }
function agent_req(array $s, string $mode, string $body = ''): array {
    $ts = (string)time(); $opt = 'up=' . (int)$s['root_up'] . ';cf=' . (int)$s['cf'];
    openssl_sign($ts . '|' . $mode . '|' . sha1($body) . '|' . $opt . '|' . host_of($s['agent_url']), $sig, gm_keys()[0], OPENSSL_ALGO_SHA256);
    $r = ['url' => $s['agent_url'] . '?m=' . $mode, 'headers' => ["X-GM-TS: $ts", "X-GM-OPT: $opt", 'X-GM-SIG: ' . base64_encode($sig)], 'timeout' => 90];
    if ($body !== '') $r['post'] = $body;
    return $r;
}
function has_agent(array $s): bool { return !empty($s['ssh_host']) || !empty($s['agent_url']); }
function agent_call(array $s, string $mode, $body = ''): ?array {
    $body = is_string($body) ? $body : json_encode($body);
    // الملفات عبر SSH إن وُجد؛ الحارس (الطلبات والحظر) دائماً عبر ملف الوكيل
    if (!empty($s['ssh_host']) && !in_array($mode, ['stats', 'setstate'], true)) return ssh_call($s, $mode, $body);
    if (!$s['agent_url']) return null;
    $r = http_multi(['a' => agent_req($s, $mode, $body)])['a'];
    $j = json_decode($r['body'], true);
    return ($r['code'] === 200 && !empty($j['ok'])) ? $j : null;
}

/* ---------- وضع SSH: تنفيذ نفس كود الوكيل على الاستضافة بدون رفع ملف ---------- */
function ssh_key_path(): string { return defined('SSH_KEY') ? SSH_KEY : dirname(__DIR__) . '/.gm-keys/id_ed25519'; }
function ssh_pubkey(bool $create = false): ?string {
    $k = ssh_key_path();
    if (!is_file($k) && $create) {
        @mkdir(dirname($k), 0700, true);
        @exec('ssh-keygen -q -t ed25519 -N "" -C ghani-monitor -f ' . escapeshellarg($k) . ' 2>&1');
        @chmod($k, 0600);
    }
    return is_file($k . '.pub') ? trim((string)file_get_contents($k . '.pub')) : null;
}
function ssh_script(array $s, string $mode, string $body): string {
    static $core, $want;
    if ($core === null) {
        $tpl = (string)file_get_contents(__DIR__ . '/agent.tpl.php');
        $core = substr($tpl, strpos($tpl, '/*GM_CORE*/'));
        preg_match('~^const GM_WANT = .*;$~m', $tpl, $m); $want = $m[0];
    }
    return "<?php\nerror_reporting(0); @set_time_limit(120); @ini_set('memory_limit', '256M');\n$want\n\$cf = false;\n"
        . '$mode = ' . var_export($mode, true) . "; \$body = base64_decode('" . base64_encode($body) . "'); \$in = json_decode(\$body, true) ?: [];\n"
        . "\$webdir = realpath(base64_decode('" . base64_encode((string)$s['ssh_path']) . "')); if (!\$webdir) { echo json_encode(['ok' => 0, 'err' => 'المسار غير موجود']); exit; }\n"
        . '$up = ' . (int)$s['root_up'] . "; \$root = realpath(\$webdir . str_repeat('/..', \$up)); \$tmp = sys_get_temp_dir() . '/gm_' . md5(\$webdir . '/gm-agent.php');\n"
        . "\$qdir = \$root . '/.gm-quarantine'; \$selfFile = \$webdir . '/gm-agent.php'; \$self = str_replace('\\\\', '/', substr(\$selfFile, strlen(\$root) + 1));\n"
        . $core;
}
function ssh_call(array $s, string $mode, string $body = ''): ?array {
    $GLOBALS['gm_ssh_err'] = '';
    if (!preg_match('~^[a-z0-9][a-z0-9._-]*$~i', (string)$s['ssh_host']) || !preg_match('~^[a-z_][a-z0-9._-]*$~i', (string)$s['ssh_user'])) { $GLOBALS['gm_ssh_err'] = 'اسم الخادم أو المستخدم غير صالح'; return null; }
    $key = ssh_key_path();
    if (!defined('GM_SSH_LOCAL') && !is_file($key)) { $GLOBALS['gm_ssh_err'] = 'لا يوجد مفتاح SSH — أنشئه من الإعدادات'; return null; }
    $cmd = defined('GM_SSH_LOCAL') ? ['php'] : ['ssh', '-i', $key, '-p', (string)(int)$s['ssh_port'], '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
        '-o', 'StrictHostKeyChecking=accept-new', '-o', 'UserKnownHostsFile=' . dirname($key) . '/known_hosts', '-o', 'ConnectTimeout=10',
        '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=8', $s['ssh_user'] . '@' . $s['ssh_host'], 'php'];
    $p = @proc_open($cmd, [['pipe', 'r'], ['pipe', 'w'], ['pipe', 'w']], $pipes);
    if (!is_resource($p)) { $GLOBALS['gm_ssh_err'] = 'تعذر تشغيل ssh على السيرفر'; return null; }
    fwrite($pipes[0], ssh_script($s, $mode, $body)); fclose($pipes[0]);
    $out = (string)stream_get_contents($pipes[1]); $err = (string)stream_get_contents($pipes[2]);
    fclose($pipes[1]); fclose($pipes[2]); proc_close($p);
    $j = json_decode($out, true);
    if (!$j || empty($j['ok'])) { $GLOBALS['gm_ssh_err'] = trim(mb_substr(($j['err'] ?? '') ?: ($err ?: $out), 0, 300)) ?: 'لا يوجد رد'; return null; }
    return $j;
}
function pack_manifest(array $files): string { return base64_encode(gzcompress(json_encode($files), 6)); }
function unpack_manifest(?string $m): array { return $m ? (json_decode((string)gzuncompress(base64_decode($m)), true) ?: []) : []; }

function tg(string $html): bool {
    $t = setting('tg_token'); $c = setting('tg_chat');
    if (!$t || !$c) return false;
    $r = http_multi(['t' => ['url' => "https://api.telegram.org/bot$t/sendMessage", 'timeout' => 10,
        'post' => http_build_query(['chat_id' => $c, 'text' => mb_substr($html, 0, 3800), 'parse_mode' => 'HTML', 'disable_web_page_preview' => 1])]])['t'];
    return $r['code'] === 200;
}

/* ================= المشاكل ================= */
function issue_open(int $sid, string $type) {
    return q('SELECT * FROM gm_issues WHERE site_id=? AND type=? AND closed_at IS NULL', [$sid, $type])->fetch();
}
function raise(array $s, string $type, string $msg, bool $again = false): void {
    $o = issue_open($s['id'], $type);
    if ($o && !$again) return;
    if ($o) q('UPDATE gm_issues SET message=? WHERE id=?', [$msg, $o['id']]);
    else q('INSERT INTO gm_issues (site_id,type,message,opened_at) VALUES (?,?,?,?)', [$s['id'], $type, $msg, now()]);
    [$icon, $label] = GM_TYPES[$type];
    tg("$icon <b>" . h($s['name']) . "</b>\n<b>$label</b>\n" . h($msg) . "\n\n" . h($s['url']) . "\n🕐 " . now());
}
function resolve(array $s, string $type): void {
    if (!issue_open($s['id'], $type)) return;
    q('UPDATE gm_issues SET closed_at=? WHERE site_id=? AND type=? AND closed_at IS NULL', [now(), $s['id'], $type]);
    tg("✅ <b>" . h($s['name']) . "</b>\nانتهت المشكلة: " . GM_TYPES[$type][1] . "\n🕐 " . now());
}
function close_silent(int $sid, array $types): void {
    foreach ($types as $t) q('UPDATE gm_issues SET closed_at=? WHERE site_id=? AND type=? AND closed_at IS NULL', [now(), $sid, $t]);
}

/* ================= المعالجة: حظر، إغلاق، عزل ================= */
function allow_ips(): array {
    return array_values(array_filter(preg_split('~[\s,]+~', (string)setting('allow_ips', '')), fn($x) => filter_var($x, FILTER_VALIDATE_IP)));
}
function block_ip(int $sid, string $ip, int $hours, string $reason, string $actor): bool {
    if (!filter_var($ip, FILTER_VALIDATE_IP) || in_array($ip, allow_ips(), true)) return false;
    q('DELETE FROM gm_blocks WHERE site_id=? AND ip=?', [$sid, $ip]);
    q('INSERT INTO gm_blocks (site_id,ip,reason,actor,at,expires) VALUES (?,?,?,?,?,?)',
        [$sid, $ip, mb_substr($reason, 0, 250), $actor, now(), $hours > 0 ? date('Y-m-d H:i:s', time() + $hours * 3600) : null]);
    act_log($sid, $actor, 'block', "$ip — $reason — " . ($hours > 0 ? "$hours ساعة" : 'دائم'));
    return true;
}
function site_state(array $s): string {
    $blk = [];
    foreach (q('SELECT ip, expires FROM gm_blocks WHERE site_id IN (0,?) AND (expires IS NULL OR expires>?) ORDER BY ip, id', [$s['id'], now()]) as $b)
        $blk[$b['ip']] = $b['expires'] ? strtotime($b['expires']) : 0;
    return json_encode(['allow' => allow_ips(), 'block' => (object)$blk, 'cf' => (int)$s['cf'], 'lock' => (int)$s['lockdown']]);
}
function push_state(array $s): bool {
    $body = site_state($s);
    $j = agent_call($s, 'setstate', $body);
    if ($j) upd($s['id'], ['state_hash' => $j['sh']]);
    return (bool)$j;
}
function push_all(int $sid = 0): void {
    foreach (q('SELECT * FROM gm_sites WHERE agent_url IS NOT NULL' . ($sid ? ' AND id=' . (int)$sid : ''))->fetchAll() as $s) push_state($s);   // الحارس فقط
}
/* زرع ملف الوكيل في المجلد العام للأصل عبر SSH. إن كانت للأصل بصمة ملفات معتمدة نضيف الملف إليها حتى لا يُحسب تغييراً مشبوهاً. */
function plant_agent(array $s): bool {
    if (empty($s['ssh_host'])) return false;
    $j = ssh_call($s, 'install', json_encode(['b64' => base64_encode(agent_code())]));
    if (!$j || empty($j['done'])) return false;
    upd($s['id'], ['agent_url' => rtrim(preg_replace('~[?#].*$~', '', $s['url']), '/') . '/gm-agent.php']);
    act_log($s['id'], 'auto', 'plant', 'زرع ملف الوكيل: ' . ($j['file'] ?? 'gm-agent.php'));
    if ($s['files_sum_base'] !== null && ($full = ssh_call($s, 'full'))) {
        $old = unpack_manifest($s['manifest']); $chg = array_keys(array_diff_assoc($full['files'], $old) + array_diff_key($old, $full['files']));
        if ($chg && !array_filter($chg, fn($p) => !preg_match('~(^|/)gm-agent\.php$~', (string)$p)))
            upd($s['id'], ['manifest' => pack_manifest($full['files']), 'files_sum_base' => $full['sum'], 'files_sum_last' => $full['sum']]);
    }
    return true;
}
function quarantine_files(array $s, array $paths, string $actor, string $reason): array {
    $j = agent_call($s, 'quarantine', ['paths' => array_values($paths)]);
    $done = [];
    foreach ($j['res'] ?? [] as $r) {
        if (empty($r['ok'])) continue;
        q('INSERT INTO gm_quarantine (site_id,path,qname,md5,sha256,size,mtime,at,reason,actor) VALUES (?,?,?,?,?,?,?,?,?,?)',
            [$s['id'], $r['path'], $r['q'], $r['md5'], $r['sha256'], (int)$r['size'], date('Y-m-d H:i:s', (int)$r['mtime']), now(), mb_substr($reason, 0, 250), $actor]);
        act_log($s['id'], $actor, 'quarantine', $r['path'] . ' — sha256: ' . $r['sha256'] . ' — ' . $reason);
        $done[] = $r['path'];
    }
    return $done;
}

/* ================= الفحوص الدورية ================= */
function host_of(string $url): string {
    return preg_replace('~^www\.~', '', strtolower((string)parse_url($url, PHP_URL_HOST)));
}
function check_page(array $s, array $r): void {
    $ok = !$r['err'] && $r['code'] >= 200 && $r['code'] < 400;
    $fails = $ok ? 0 : $s['fail_count'] + 1;
    upd($s['id'], ['http_code' => $r['code'], 'resp_ms' => $r['ms'], 'fail_count' => $fails]);
    if (!$ok) {
        if ($fails >= 2) raise($s, 'down', 'الموقع لا يستجيب: ' . ($r['err'] ?: ($r['code'] ? 'HTTP ' . $r['code'] : 'لا يوجد اتصال (انقطاع أو مهلة)')));
        return;
    }
    resolve($s, 'down');
    $body = $r['body']; $own = host_of($s['url']); $final = host_of($r['final']);

    if ($final && $final !== $own) raise($s, 'redirect', "الموقع يحوّل الزوار إلى: $final");
    else resolve($s, 'redirect');

    $title = preg_match('~<title[^>]*>(.*?)</title>~is', $body, $m) ? mb_substr(trim(html_entity_decode($m[1], ENT_QUOTES, 'UTF-8')), 0, 250) : '';
    if ($s['title_base'] === null) upd($s['id'], ['title_base' => $title]);
    elseif ($title !== $s['title_base']) raise($s, 'title', "القديم: {$s['title_base']}\nالجديد: $title");
    else resolve($s, 'title');

    preg_match_all('~<(?:script|iframe)\b[^>]*?\bsrc\s*=\s*["\']?(?:https?:)?//([^/"\'\s>:]+)~i', $body, $mm);
    $hosts = array_values(array_unique(array_diff(array_map(fn($x) => preg_replace('~^www\.~', '', strtolower($x)), $mm[1]), [$own])));
    if ($s['hosts_base'] === null) upd($s['id'], ['hosts_base' => json_encode($hosts)]);
    else {
        $new = array_diff($hosts, json_decode($s['hosts_base'], true) ?: []);
        if ($new) raise($s, 'scripts', "مصادر جديدة لم تكن موجودة:\n" . implode("\n", $new));
        else resolve($s, 'scripts');
    }

    $re = '~h[a4]ck[e3]d\s+by|defaced\s+by|pwn[e3]d\s+by|تم\s+ال?اختراق~iu';
    if (preg_match($re, $title . ($s['deface_check'] ? ' ' . $body : ''), $d)) raise($s, 'deface', 'وُجدت عبارة: ' . $d[0]);
    else resolve($s, 'deface');

    if ($s['keyword'] !== '') {
        if (mb_stripos($body, $s['keyword']) === false) raise($s, 'keyword', "الكلمة «{$s['keyword']}» اختفت من الصفحة");
        else resolve($s, 'keyword');
    }
}
function check_files(array $s, array $r): void {
    $j = json_decode($r['body'], true);
    if ($r['code'] !== 200 || empty($j['ok'])) {
        if ($s['agent_ok'] === null) return;                      // لم يُرفع الوكيل بعد
        upd($s['id'], ['agent_ok' => 0, 'agent_fail' => $s['agent_fail'] + 1]);
        if ($s['agent_fail'] + 1 >= 2 && $s['fail_count'] == 0)
            raise($s, 'agent', !empty($s['ssh_host']) ? 'تعذر الاتصال عبر SSH: ' . ($r['err'] ?? '') : 'ملف الوكيل حُذف أو عُدّل أو مُنع الوصول إليه (HTTP ' . $r['code'] . ')');
        return;
    }
    upd($s['id'], ['agent_ok' => 1, 'agent_fail' => 0, 'files_count' => (int)$j['count']]);
    resolve($s, 'agent');
    $sum = $j['sum'];

    if ($s['files_sum_base'] === null) {                           // أول بصمة
        if ($full = agent_call($s, 'full'))
            upd($s['id'], ['manifest' => pack_manifest($full['files']), 'files_sum_base' => $full['sum'], 'files_sum_last' => $full['sum']]);
        return;
    }
    if ($sum === $s['files_sum_base']) {
        if ($s['files_sum_last'] !== $sum) upd($s['id'], ['files_sum_last' => $sum, 'files_diff' => null]);
        resolve($s, 'files');
        return;
    }
    if ($sum === $s['files_sum_last']) return;                     // نفس التغيير، تم التبليغ سابقاً

    if (!($full = agent_call($s, 'full'))) return;
    $old = unpack_manifest($s['manifest']); $new = $full['files'];
    $added = array_map('strval', array_keys(array_diff_key($new, $old)));
    $removed = array_map('strval', array_keys(array_diff_key($old, $new)));
    $mod = [];
    foreach (array_intersect_key($new, $old) as $p => $hsh) if ($old[$p] !== $hsh) $mod[] = (string)$p;

    $ins = agent_call($s, 'inspect', array_slice(array_merge($added, $mod), 0, 300));
    $sus = []; $strong = [];
    foreach ($ins['sus'] ?? [] as $p => $m) { $sus[$p] = array_merge($m['s'], $m['w']); if ($m['s']) $strong[] = (string)$p; }

    // سجل التحقيق: لا نكرر ما سُجّل لنفس التغيير
    $prev = json_decode($s['files_diff'] ?? '', true) ?: ['added' => [], 'mod' => [], 'removed' => []];
    foreach (['added' => $added, 'mod' => $mod, 'removed' => $removed] as $chg => $list)
        foreach (array_slice(array_diff($list, $prev[$chg] ?? []), 0, 200) as $p)
            q('INSERT INTO gm_filelog (site_id,at,path,chg,sus) VALUES (?,?,?,?,?)', [$s['id'], now(), mb_substr($p, 0, 500), $chg, isset($sus[$p]) ? implode('، ', $sus[$p]) : null]);

    // استجابة تلقائية: عزل الملفات الجديدة ذات التوقيع القوي
    $auto = [];
    if (setting('auto_quarantine') === '1' && ($hit = array_values(array_intersect($added, $strong))))
        $auto = quarantine_files($s, $hit, 'auto', 'عزل تلقائي: ' . implode('، ', $sus[$hit[0]]));

    upd($s['id'], ['files_sum_last' => $full['sum'], 'files_diff' => jenc(compact('added', 'mod', 'removed', 'sus', 'strong'))]);

    $newExec = array_filter($added, fn($p) => preg_match('~\.(php\d?|phtml|phar|pht)(\.|$)~i', $p));
    $msg = ($strong ? "⛔ كود خبيث مؤكد التوقيع (Webshell/Backdoor)\n" : ($sus ? "⚠️ مؤشرات مشبوهة تحتاج مراجعة\n" : ($newExec ? "⛔ ملفات PHP جديدة لم تكن موجودة\n" : "قد يكون تحديثاً منك — راجع واعتمد من اللوحة\n")));
    $msg .= '➕ جديدة: ' . count($added) . ' | ✏️ معدّلة: ' . count($mod) . ' | ➖ محذوفة: ' . count($removed) . "\n";
    foreach (array_slice($sus, 0, 8, true) as $p => $why) $msg .= "\n☠️ $p\n   ← " . implode('، ', $why);
    foreach (array_slice($added, 0, 8) as $p) if (!isset($sus[$p])) $msg .= "\n➕ $p";
    foreach (array_slice($mod, 0, 8) as $p) if (!isset($sus[$p])) $msg .= "\n✏️ $p";
    foreach (array_slice($removed, 0, 4) as $p) $msg .= "\n➖ $p";
    if ($auto) $msg .= "\n\n🧹 تم عزلها تلقائياً:\n" . implode("\n", $auto);
    raise($s, 'files', $msg, true);
}
function check_traffic(array $s, array $r): void {
    $j = json_decode($r['body'], true);
    if ($r['code'] !== 200 || empty($j['ok'])) return;
    if (($j['sh'] ?? '') !== md5(site_state($s))) push_state($s);          // مزامنة قائمة الحظر والإغلاق
    $prev = $s['traffic_at'];
    upd($s['id'], ['traffic_at' => now()]);

    if (!empty($j['rows'])) {
        db()->beginTransaction();
        $st = db()->prepare('INSERT INTO gm_requests (site_id,at,ip,method,path,ua,tag) VALUES (?,?,?,?,?,?,?)');
        foreach ($j['rows'] as $w) $st->execute([$s['id'], date('Y-m-d H:i:s', (int)$w[0]), substr((string)$w[1], 0, 45), substr((string)$w[2], 0, 8),
            mb_substr((string)$w[3], 0, 300), mb_substr((string)$w[4], 0, 120), (string)$w[5]]);
        db()->commit();
    }
    if (!$prev || (!$j['total'] && !$j['blocked'] && !$s['traffic_last'])) return;   // أول قراءة، أو الحارس غير مربوط بعد
    $f = 300 / max(60, time() - strtotime($prev));                                   // تطبيع إلى «لكل 5 دقائق»
    $total = (int)round($j['total'] * $f);
    $ip = array_key_first($j['ips']);    $ipN = (int)round(($j['ips'][$ip] ?? 0) * $f);
    $bip = array_key_first($j['login']); $bN = (int)round(($j['login'][$bip] ?? 0) * $f);
    [$avg, $n] = array_values(q('SELECT COALESCE(AVG(total),0) a, COUNT(*) c FROM gm_traffic WHERE site_id=? AND at>?', [$s['id'], ago(86400)])->fetch());
    q('INSERT INTO gm_traffic (site_id,at,total) VALUES (?,?,?)', [$s['id'], now(), $total]);
    unset($j['rows']);
    upd($s['id'], ['traffic_last' => jenc(['total' => $total] + $j)]);

    $top = function (array $a, int $k = 3) { $o = ''; foreach (array_slice($a, 0, $k, true) as $x => $c) $o .= "\n  $x ← $c"; return $o; };
    $offend = [];                                                                    // ip => سبب
    $atkMin = (int)setting('atk_min', 5); $lines = '';
    foreach ($j['atk'] as $aip => $tags) {
        if (array_sum($tags) < $atkMin) continue;
        $d = implode('، ', array_map(fn($t, $c) => (GM_TAGS[$t] ?? $t) . "×$c", array_keys($tags), $tags));
        $offend[(string)$aip] = "هجوم: $d"; $lines .= "\n  $aip ← $d";
    }
    $isFlood = $total >= (int)setting('rq_min', 500) && ($n < 12 || $total >= 4 * $avg);
    $isIp = $ipN >= (int)setting('ip_max', 300);
    $isBrute = $bN >= (int)setting('login_max', 20);
    if ($isBrute) $offend[(string)$bip] = ($offend[(string)$bip] ?? '') . " Brute force ×$bN";
    if ($isIp) $offend[(string)$ip] = ($offend[(string)$ip] ?? '') . " إغراق ×$ipN";

    $note = '';
    if ($offend && setting('auto_block') === '1') {
        $hrs = max(1, (int)setting('block_hours', 24)); $done = [];
        foreach ($offend as $oip => $why) if (block_ip($s['id'], $oip, $hrs, trim($why), 'auto')) $done[] = $oip;
        if ($done) { push_state($s); $note = "\n\n⛔ حُظرت تلقائياً لمدة $hrs ساعة:\n  " . implode("\n  ", $done); }
    }
    if ($lines) raise($s, 'attack', "خلال 5 دقائق:$lines$note"); else resolve($s, 'attack');
    if ($isFlood) raise($s, 'flood', "$total طلب خلال 5 دقائق" . ($n >= 12 ? ' (المعدل الطبيعي ~' . round($avg) . ')' : '') . "\nعدد الـ IPs: {$j['uniq']}\nأكثر الـ IPs:" . $top($j['ips']) . "\nأكثر المسارات:" . $top($j['paths']));
    else resolve($s, 'flood');
    if ($isIp) raise($s, 'ipflood', "أكثر الـ IPs خلال 5 دقائق:" . $top($j['ips']) . "\nالمسارات:" . $top($j['paths']) . $note); else resolve($s, 'ipflood');
    if ($isBrute) raise($s, 'brute', "محاولات POST على صفحات الدخول خلال 5 دقائق:" . $top($j['login']) . $note); else resolve($s, 'brute');
}
function check_ssl_dns(array $s): void {
    $host = (string)parse_url($s['url'], PHP_URL_HOST);
    upd($s['id'], ['ssl_checked_at' => now()]);
    // DNS: خوادم الأسماء (NS) — تغيّرها بدون علمك مؤشر على اختطاف النطاق
    $ns = []; $d = $host;
    while (substr_count($d, '.') >= 1 && !$ns) {
        foreach ((array)@dns_get_record($d, DNS_NS) as $rr) if (!empty($rr['target'])) $ns[] = strtolower($rr['target']);
        $d = (string)substr($d, strpos($d, '.') + 1);
    }
    if ($ns) {
        sort($ns); $cur = implode(', ', array_unique($ns));
        if ($s['dns_base'] === null) upd($s['id'], ['dns_base' => $cur]);
        elseif ($cur !== $s['dns_base']) raise($s, 'dns', "السابق: {$s['dns_base']}\nالحالي: $cur\nإذا التغيير منك اضغط «اعتماد الصفحة».");
        else resolve($s, 'dns');
    }
    if (stripos($s['url'], 'https://') !== 0) return;
    $ctx = stream_context_create(['ssl' => ['capture_peer_cert' => true, 'verify_peer' => false, 'verify_peer_name' => false, 'peer_name' => $host]]);
    $c = @stream_socket_client("ssl://$host:443", $e, $es, 8, STREAM_CLIENT_CONNECT, $ctx);
    if (!$c) return;
    $cert = openssl_x509_parse(stream_context_get_params($c)['options']['ssl']['peer_certificate'] ?? '');
    fclose($c);
    if (empty($cert['validTo_time_t'])) return;
    $exp = (int)$cert['validTo_time_t'];
    upd($s['id'], ['ssl_expires' => date('Y-m-d H:i:s', $exp)]);
    $days = (int)floor(($exp - time()) / 86400);
    if ($days < 7) raise($s, 'ssl', $days < 0 ? 'الشهادة منتهية!' : "الشهادة تنتهي خلال $days يوم");
    else resolve($s, 'ssl');
}

/* ================= التدقيق الأمني (ثغرات وإعدادات) ================= */
function security_audit(array $s): array {
    $fd = [];
    $base = rtrim(preg_replace('~[?#].*$~', '', $s['url']), '/'); $host = (string)parse_url($s['url'], PHP_URL_HOST);
    $sec = 'امنع الوصول إليه أو احذفه، وغيّر أي كلمات سر كانت بداخله.';
    $probes = [
        ['/.env', '~^\s*(APP_KEY|DB_PASSWORD|DB_HOST|APP_ENV)\s*=~m', 'high', 'ملف ‎.env مكشوف للعامة', 'يحتوي كلمات سر قاعدة البيانات ومفاتيح التطبيق. ' . $sec],
        ['/.git/config', '~\[core\]~', 'high', 'مستودع ‎.git مكشوف للعامة', 'يمكن سحب كامل الكود المصدري وسجل التعديلات. ' . $sec],
        ['/storage/logs/laravel.log', '~\]\s\w+\.(ERROR|INFO|WARNING|DEBUG)|Stack trace~', 'high', 'سجل Laravel مكشوف للعامة', 'يكشف مسارات واستعلامات وربما بيانات مستخدمين. الجذر يجب أن يشير إلى public فقط.'],
        ['/phpinfo.php', '~<title>phpinfo\(\)|PHP Version~', 'med', 'صفحة phpinfo مكشوفة', 'تكشف إعدادات السيرفر كاملة. احذفها.'],
        ['/info.php', '~<title>phpinfo\(\)|PHP Version~', 'med', 'صفحة phpinfo مكشوفة (info.php)', 'تكشف إعدادات السيرفر كاملة. احذفها.'],
        ['/adminer.php', '~adminer~i', 'med', 'Adminer مكشوف', 'واجهة قاعدة بيانات متاحة للعامة. احذفه أو قيّده بـ IP.'],
        ['/phpmyadmin/', '~phpMyAdmin~', 'low', 'phpMyAdmin متاح على مسار معروف', 'قيّده بـ IP أو غيّر المسار.'],
        ['/composer.json', '~"require"\s*:~', 'low', 'composer.json مكشوف', 'يكشف المكتبات وإصداراتها للمهاجم.'],
        ['/wp-config.php.bak', '~DB_PASSWORD|<\?php~', 'high', 'نسخة احتياطية من wp-config مكشوفة', $sec],
        ['/config.php.bak', '~<\?php|password~i', 'high', 'نسخة احتياطية من config مكشوفة', $sec],
        ['/server-status', '~Apache Server Status~', 'low', 'server-status مكشوف', 'يكشف الطلبات الحالية على السيرفر.'],
        ['/uploads/', '~<title>Index of /~i', 'med', 'عرض محتويات المجلدات مفعّل (uploads)', 'أضف Options -Indexes أو ملف index فارغ.'],
    ];
    foreach (['backup.sql', 'db.sql', 'database.sql', 'dump.sql'] as $n) $probes[] = ["/$n", '~CREATE TABLE|INSERT INTO|-- MySQL dump~i', 'high', "نسخة قاعدة بيانات مكشوفة ($n)", 'أي شخص يستطيع تنزيل قاعدة البيانات كاملة. احذفها فوراً وغيّر كلمات السر.'];
    foreach (['backup.zip', 'public_html.zip', 'www.zip', 'site.zip', "$host.zip"] as $n) $probes[] = ["/$n", '~^PK\x03\x04~', 'high', "أرشيف الموقع مكشوف ($n)", 'يمكن تنزيل كامل الكود والإعدادات. احذفه.'];
    $reqs = ['_main' => ['url' => $s['url'], 'hdr' => 1], '_http' => ['url' => 'http://' . $host . '/', 'nofollow' => 1, 'hdr' => 1, 'timeout' => 10]];
    foreach ($probes as $i => $p) $reqs["p$i"] = ['url' => $base . $p[0], 'nofollow' => 1, 'range' => '0-4095', 'timeout' => 12];
    $res = http_multi($reqs, 15);
    foreach ($probes as $i => $p) { $r = $res["p$i"]; if (in_array($r['code'], [200, 206], true) && preg_match($p[1], $r['body'])) $fd[] = [$p[2], $p[3], $base . $p[0] . "\n" . $p[4]]; }

    $hd = strtolower($res['_main']['hdr']);
    if ($hd) {
        $https = stripos($s['url'], 'https://') === 0;
        if (!$https) $fd[] = ['high', 'الموقع يعمل بدون HTTPS', 'كلمات السر والجلسات تُرسل بدون تشفير. فعّل SSL.'];
        elseif (!preg_match('~^location:\s*https://~mi', $res['_http']['hdr'])) $fd[] = ['med', 'لا يوجد تحويل تلقائي من HTTP إلى HTTPS', 'أضف تحويل 301 إلى https.'];
        $miss = [];
        if ($https && strpos($hd, 'strict-transport-security:') === false) $miss[] = 'Strict-Transport-Security';
        if (strpos($hd, 'x-frame-options:') === false && strpos($hd, 'frame-ancestors') === false) $miss[] = 'X-Frame-Options';
        if (strpos($hd, 'x-content-type-options:') === false) $miss[] = 'X-Content-Type-Options';
        if (strpos($hd, 'content-security-policy:') === false) $miss[] = 'Content-Security-Policy';
        if ($miss) $fd[] = ['low', 'ترويسات حماية ناقصة', implode(', ', $miss) . "\nأضفها من إعدادات السيرفر أو ‎.htaccess."];
        if (preg_match('~^x-powered-by:\s*(.+)$~mi', $res['_main']['hdr'], $m)) $fd[] = ['low', 'كشف إصدار التقنية (X-Powered-By)', trim($m[1]) . "\nعطّل expose_php."];
        if (preg_match_all('~^set-cookie:\s*([^=]+)=[^\n]*$~mi', $res['_main']['hdr'], $ck, PREG_SET_ORDER)) {
            $bad = [];
            foreach ($ck as $c) if (stripos($c[0], 'httponly') === false || ($https && stripos($c[0], 'secure') === false)) $bad[] = trim($c[1]);
            if ($bad) $fd[] = ['med', 'كوكيز بدون HttpOnly/Secure', implode(', ', array_unique($bad)) . "\nتسهّل سرقة الجلسة عبر XSS أو شبكة غير مشفّرة."];
        }
    }
    $info = [];
    if (has_agent($s) && ($a = agent_call($s, 'audit'))) { $fd = array_merge($fd, $a['findings']); $info = $a['info']; }

    $w = ['high' => 0, 'med' => 0, 'low' => 0];
    foreach ($fd as $x) $w[$x[0]]++;
    usort($fd, fn($a, $b) => array_search($a[0], ['high', 'med', 'low']) <=> array_search($b[0], ['high', 'med', 'low']));
    $score = max(0, 100 - 25 * $w['high'] - 8 * $w['med'] - 2 * $w['low']);
    $highs = array_values(array_map(fn($x) => $x[1], array_filter($fd, fn($x) => $x[0] === 'high')));
    $hh = md5(implode('|', $highs));
    $old = json_decode($s['audit'] ?? '', true) ?: [];
    upd($s['id'], ['audit' => jenc(['findings' => $fd, 'info' => $info, 'hh' => $hh]), 'audit_at' => now(), 'score' => $score]);
    if ($highs) raise($s, 'vuln', "درجة الأمان: $score/100\n• " . implode("\n• ", $highs) . "\nالتفاصيل والحلول في اللوحة.", ($old['hh'] ?? '') !== $hh);
    else resolve($s, 'vuln');
    return $fd;
}

/* ================= الفحص العميق للكود الخبيث ================= */
function deep_scan(array $s, int $budget = 90): ?bool {
    $st = json_decode($s['scan'] ?? '', true) ?: [];
    if (!$st || !empty($st['done'])) $st = ['skip' => 0, 'hits' => [], 'scanned' => 0, 'done' => 0, 'hh' => $st['hh'] ?? ''];
    $t0 = time();
    do {
        if (!($j = agent_call($s, 'scan', ['skip' => $st['skip']]))) return null;
        $st['hits'] = array_merge($st['hits'], $j['hits']); $st['scanned'] += $j['scanned']; $st['skip'] = $j['next']; $st['done'] = $j['done'];
    } while (!$st['done'] && time() - $t0 < $budget);
    if ($st['done']) {
        $ign = json_decode($s['scan_ignore'] ?? '', true) ?: [];
        $strong = [];
        foreach ($st['hits'] as $x) if ($x[1] && !in_array($x[0], $ign, true)) $strong[$x[0]] = $x[1];
        $hh = md5(implode('|', array_keys($strong)));
        if ($strong) {
            $msg = 'فُحص ' . $st['scanned'] . " ملف — ملفات بتوقيع خبيث:";
            foreach (array_slice($strong, 0, 10, true) as $p => $why) $msg .= "\n☠️ $p\n   ← " . implode('، ', $why);
            raise($s, 'malware', $msg, $st['hh'] !== $hh);
        } else resolve($s, 'malware');
        $st['hh'] = $hh;
    }
    $st['at'] = now();
    upd($s['id'], ['scan' => jenc($st)] + ($st['done'] ? ['scan_at' => now()] : []));
    return (bool)$st['done'];
}

function daily_summary(): void {
    if (setting('last_summary') === date('Y-m-d') || (int)date('G') < 9) return;
    set_setting('last_summary', date('Y-m-d'));
    $sites = (int)q('SELECT COUNT(*) FROM gm_sites')->fetchColumn();
    $open = q('SELECT s.name, i.type FROM gm_issues i JOIN gm_sites s ON s.id=i.site_id WHERE i.closed_at IS NULL')->fetchAll();
    $atk = (int)q("SELECT COUNT(*) FROM gm_requests WHERE tag<>'' AND at>?", [ago(86400)])->fetchColumn();
    $blk = (int)q('SELECT COUNT(*) FROM gm_blocks WHERE expires IS NULL OR expires>?', [now()])->fetchColumn();
    $low = q('SELECT name, score FROM gm_sites WHERE score IS NOT NULL ORDER BY score LIMIT 3')->fetchAll();
    $m = "📊 <b>GHANI Monitor — الملخص اليومي</b>\nالمواقع: $sites | مشاكل مفتوحة: " . count($open) . "\nطلبات هجومية (24 ساعة): $atk | IPs محظورة: $blk";
    foreach ($open as $o) $m .= "\n• " . h($o['name']) . ': ' . GM_TYPES[$o['type']][1];
    if ($low) { $m .= "\n\nأقل درجات الأمان:"; foreach ($low as $l) $m .= "\n• " . h($l['name']) . ": {$l['score']}/100"; }
    tg($m);
}

function run_checks(): bool {
    $lock = fopen(sys_get_temp_dir() . '/gm_' . md5(__DIR__) . '.lock', 'c');
    if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) return false;
    @set_time_limit(290);
    $sites = q('SELECT * FROM gm_sites ORDER BY id')->fetchAll();
    $reqs = [];
    foreach ($sites as $s) {
        if (!$s['lockdown']) $reqs['p' . $s['id']] = ['url' => $s['url']];
        if ($s['agent_url'] && !$s['ssh_host']) $reqs['a' . $s['id']] = agent_req($s, 'sum');
        if ($s['agent_url']) $reqs['t' . $s['id']] = agent_req($s, 'stats');
    }
    $res = $reqs ? http_multi($reqs) : [];
    $sshDue = []; $every = max(5, (int)setting('files_every', 30)) * 60;
    foreach ($sites as $s) {
        try {
            if (isset($res['p' . $s['id']])) {
                check_page($s, $res['p' . $s['id']]);
                $s['fail_count'] = (!$res['p' . $s['id']]['err'] && $res['p' . $s['id']]['code'] < 400) ? 0 : 1;
            }
            if ($s['ssh_host']) { if (!$s['files_at'] || strtotime($s['files_at']) < time() - $every + 60) $sshDue[] = $s; }
            elseif ($s['agent_url']) check_files($s, $res['a' . $s['id']]);
            if ($s['agent_url']) check_traffic($s, $res['t' . $s['id']]);
            if (!$s['ssl_checked_at'] || strtotime($s['ssl_checked_at']) < time() - 21600) check_ssl_dns($s);
            upd($s['id'], ['last_check' => now()]);
        } catch (Throwable $e) { if (db()->inTransaction()) db()->rollBack(); error_log('GM site ' . $s['id'] . ': ' . $e->getMessage()); }
    }
    // فحص الملفات عبر SSH: الأقدم أولاً، وبميزانية وقت لكل دورة حتى لا تُرهق الاستضافة المشتركة ولا تتأخر التنبيهات
    usort($sshDue, fn($a, $b) => strcmp((string)$a['files_at'], (string)$b['files_at']));
    $t0 = time();
    foreach ($sshDue as $s) {
        if (time() - $t0 > 150) break;
        try {
            if (!$s['agent_url'] && setting('auto_plant') === '1' && plant_agent($s)) $s = site((int)$s['id']) + ['fail_count' => $s['fail_count']];
            $j = ssh_call($s, 'sum');
            upd($s['id'], ['files_at' => now()]);
            check_files($s, ['code' => $j ? 200 : 0, 'body' => $j ? json_encode($j) : '', 'err' => $GLOBALS['gm_ssh_err']]);
        } catch (Throwable $e) { error_log('GM ssh ' . $s['id'] . ': ' . $e->getMessage()); }
    }
    // مهام ثقيلة: موقع واحد لكل دورة حتى لا تتأخر الفحوص
    try {
        if ($s = q('SELECT * FROM gm_sites WHERE lockdown=0 AND (audit_at IS NULL OR audit_at<?) ORDER BY audit_at LIMIT 1', [ago(86400)])->fetch()) security_audit($s);
        if ($s = q("SELECT * FROM gm_sites WHERE agent_ok=1 AND (scan_at IS NULL OR scan_at<? OR scan LIKE '%\"done\":0%') ORDER BY scan_at LIMIT 1", [ago(86400)])->fetch()) deep_scan($s);
    } catch (Throwable $e) { error_log('GM heavy: ' . $e->getMessage()); }
    q('DELETE FROM gm_traffic WHERE at<?', [ago(7 * 86400)]);
    q('DELETE FROM gm_requests WHERE at<?', [ago(max(1, (int)setting('keep_days', 7)) * 86400)]);
    q('DELETE FROM gm_blocks WHERE expires IS NOT NULL AND expires<?', [ago(7 * 86400)]);
    daily_summary();
    set_setting('last_cron', now());
    flock($lock, LOCK_UN);
    return true;
}
