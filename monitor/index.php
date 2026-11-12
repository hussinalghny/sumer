<?php
require __DIR__ . '/lib.php';
require __DIR__ . '/views.php';
session_set_cookie_params(['httponly' => true, 'samesite' => 'Lax', 'secure' => !empty($_SERVER['HTTPS'])]);
session_start();
try { migrate(); } catch (Throwable $e) { exit('تعذر الاتصال بقاعدة البيانات — راجع config.php'); }

$csrf = $_SESSION['csrf'] ??= bin2hex(random_bytes(16));
$act = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!hash_equals($csrf, (string)($_POST['csrf'] ?? ''))) exit('bad csrf');
    $act = (string)($_POST['act'] ?? '');
}
$SELF = strtok($_SERVER['REQUEST_URI'], '?');
function back(string $msg = '', ?string $to = null): void {
    global $SELF;
    $ret = $to ?? (string)($_POST['ret'] ?? '');
    $_SESSION['flash'] = $msg;
    header('Location: ' . $SELF . (preg_match('~^\?[\w=&%.:\-+/]*$~', $ret) ? $ret : '')); exit;
}

/* ---------- الإعداد الأول وتسجيل الدخول ---------- */
if (!setting('admin_hash')) {
    $err = '';
    if ($act === 'setup') {
        if (hash_equals(CRON_KEY, (string)($_POST['key'] ?? '')) && strlen((string)($_POST['pass'] ?? '')) >= 10 && CRON_KEY !== 'CHANGE_ME_TO_LONG_RANDOM_STRING') {
            set_setting('admin_hash', password_hash($_POST['pass'], PASSWORD_DEFAULT));
            session_regenerate_id(true); $_SESSION['in'] = 1; back('تم إنشاء الحساب ✅', '?v=settings');
        }
        $err = 'المفتاح خاطئ (أو لم تغيّر CRON_KEY في config.php) أو كلمة المرور أقل من 10 أحرف';
    }
    page_top('إعداد المراقب', false); ?>
    <section class="pn"><h2>GHANI SOC: الإعداد الأول</h2><div class="pb"><?= $err ? "<div class='note'>$err</div>" : '' ?>
    <form method="post"><?= csrf_in() ?><input type="hidden" name="act" value="setup">
    <label>مفتاح CRON_KEY (من config.php)</label><input type="password" name="key" required>
    <label>كلمة مرور اللوحة (10 أحرف فأكثر)</label><input type="password" name="pass" minlength="10" required>
    <p><button class="btn pri">إنشاء الحساب</button></p></form></div></section><?php page_end(); exit;
}
if (empty($_SESSION['in'])) {
    $err = '';
    if ($act === 'login') {
        $fails = (int)setting('login_fails', 0); $until = (int)setting('login_lock', 0);
        if ($until > time()) $err = 'محاولات كثيرة — انتظر ' . ceil(($until - time()) / 60) . ' دقيقة';
        elseif (password_verify((string)($_POST['pass'] ?? ''), setting('admin_hash'))) {
            set_setting('login_fails', '0'); session_regenerate_id(true); $_SESSION['in'] = 1;
            act_log(0, 'admin', 'login', 'دخول من ' . ($_SERVER['REMOTE_ADDR'] ?? '')); back();
        } else {
            sleep(2); set_setting('login_fails', (string)++$fails);
            if ($fails >= 5) { set_setting('login_lock', (string)(time() + 900)); set_setting('login_fails', '0'); tg("🔐 <b>GHANI Monitor</b>\n5 محاولات دخول فاشلة للوحة من " . h($_SERVER['REMOTE_ADDR'] ?? '')); }
            $err = 'كلمة المرور غير صحيحة';
        }
    }
    page_top('دخول', false); ?>
    <section class="pn"><h2>GHANI SOC: تسجيل الدخول</h2><div class="pb"><?= $err ? "<div class='note'>$err</div>" : '' ?>
    <form method="post"><?= csrf_in() ?><input type="hidden" name="act" value="login">
    <label>كلمة المرور</label><input type="password" name="pass" autofocus required><p><button class="btn pri">دخول</button></p></form></div></section><?php page_end(); exit;
}

/* ---------- تنزيل الوكيل ---------- */
if (isset($_GET['agent'])) {
    $s = site((int)$_GET['agent']) ?: exit('not found');
    $code = strtr(file_get_contents(__DIR__ . '/agent.tpl.php'), ['__GM_SECRET__' => $s['secret'],
        'GM_UP = 0; /*__GM_UP__*/' => 'GM_UP = ' . (int)$s['root_up'] . ';',
        "define('GM_CF', false); /*__GM_CF__*/" => "define('GM_CF', " . ($s['cf'] ? 'true' : 'false') . ');']);
    header('Content-Type: application/octet-stream'); header('Content-Disposition: attachment; filename="gm-agent.php"');
    exit($code);
}

/* ---------- الإجراءات ---------- */
$sid = (int)($_POST['id'] ?? 0);
$S = $sid ? site($sid) : null;
switch ($act) {
    case 'logout': session_destroy(); header('Location: ' . $SELF); exit;
    case 'add':
        $url = trim((string)$_POST['url']);
        if (!filter_var($url, FILTER_VALIDATE_URL) || !preg_match('~^https?://~i', $url)) back('الرابط غير صحيح');
        $agent = empty($_POST['agent']) ? null : rtrim(preg_replace('~[?#].*$~', '', $url), '/') . '/gm-agent.php';
        $sh = trim((string)($_POST['ssh_host'] ?? '')); $su = trim((string)($_POST['ssh_user'] ?? '')); $sp = trim((string)($_POST['ssh_path'] ?? ''));
        if ($sh !== '' && (!preg_match('~^[a-z0-9][a-z0-9._-]*$~i', $sh) || !preg_match('~^[a-z_][a-z0-9._-]*$~i', $su) || $sp === '' || $sp[0] !== '/')) back('بيانات SSH غير صحيحة (الخادم، المستخدم، ومسار كامل يبدأ بـ /)');
        q('INSERT INTO gm_sites (name,url,keyword,deface_check,agent_url,secret,root_up,cf,ssh_host,ssh_port,ssh_user,ssh_path,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
            [mb_substr(trim((string)$_POST['name']) ?: host_of($url), 0, 120), $url, mb_substr(trim((string)$_POST['keyword']), 0, 120),
             empty($_POST['deface']) ? 0 : 1, $agent, bin2hex(random_bytes(24)), (int)!empty($_POST['laravel']), (int)!empty($_POST['cf']),
             $sh ?: null, max(1, (int)($_POST['ssh_port'] ?? 22)), $sh ? $su : null, $sh ? rtrim($sp, '/') : null, now()]);
        back($sh ? 'تمت الإضافة — اضغط «اختبار SSH» للتأكد من الاتصال' : ($agent ? 'تمت الإضافة — نزّل ملف الوكيل وارفعه' : 'تمت الإضافة'), '?site=' . db()->lastInsertId());
    case 'sshtest':
        if ($S && $S['ssh_host']) { $j = ssh_call($S, 'sum'); back($j ? '✅ الاتصال ناجح — ' . (int)$j['count'] . ' ملف كود' : '❌ فشل: ' . $GLOBALS['gm_ssh_err']); }
        back();
    case 'sshkey': back(ssh_pubkey(true) ? 'المفتاح جاهز' : 'تعذر إنشاء المفتاح — تأكد أن ssh-keygen متوفر وأن مستخدم الويب يستطيع الكتابة في ' . dirname(ssh_key_path()));
    case 'del':
        if ($S) foreach (['gm_issues', 'gm_traffic', 'gm_filelog', 'gm_requests', 'gm_blocks', 'gm_quarantine', 'gm_actions'] as $t) q("DELETE FROM $t WHERE site_id=?", [$sid]);
        if ($S) q('DELETE FROM gm_sites WHERE id=?', [$sid]);
        back('تم الحذف', '?v=assets');
    case 'ok_files':
        if ($S && ($full = agent_call($S, 'full'))) {
            upd($sid, ['manifest' => pack_manifest($full['files']), 'files_sum_base' => $full['sum'], 'files_sum_last' => $full['sum'], 'files_diff' => null]);
            close_silent($sid, ['files']); act_log($sid, 'admin', 'approve', 'اعتماد الملفات الحالية كبصمة (' . count($full['files']) . ' ملف)');
            back('تم اعتماد الملفات الحالية كبصمة جديدة');
        }
        back('تعذر الاتصال بالوكيل');
    case 'ok_page':
        if ($S) { upd($sid, ['title_base' => null, 'hosts_base' => null, 'dns_base' => null, 'ssl_checked_at' => null]); close_silent($sid, ['title', 'scripts', 'dns']); act_log($sid, 'admin', 'approve', 'اعتماد شكل الصفحة و DNS'); }
        back('سيُعتمد الوضع الحالي في الفحص القادم');
    case 'audit':
        if ($S) { $n = count(security_audit($S)); act_log($sid, 'admin', 'audit', "تدقيق أمني يدوي: $n ملاحظة"); back("انتهى التدقيق: $n ملاحظة"); }
        back();
    case 'scan':
        if ($S) {
            upd($sid, ['scan' => null]); $S['scan'] = null;
            $r = deep_scan($S, 50); act_log($sid, 'admin', 'scan', 'فحص عميق يدوي');
            back($r === null ? 'تعذر الاتصال بالوكيل' : ($r ? 'انتهى الفحص العميق' : 'الموقع كبير — الفحص مستمر تلقائياً بالخلفية كل 5 دقائق'));
        }
        back();
    case 'lock': case 'unlock':
        if ($S) {
            upd($sid, ['lockdown' => $act === 'lock' ? 1 : 0]); $ok = push_state(site($sid));
            act_log($sid, 'admin', $act, $act === 'lock' ? 'تفعيل الإغلاق الطارئ' : 'إلغاء الإغلاق الطارئ');
            tg(($act === 'lock' ? '🔒' : '🔓') . ' <b>' . h($S['name']) . "</b>\n" . ($act === 'lock' ? 'تم تفعيل الإغلاق الطارئ' : 'تم إلغاء الإغلاق الطارئ'));
            back($ok ? ($act === 'lock' ? 'الموقع مغلق الآن للجميع عدا الـ IPs المستثناة' : 'تم فتح الموقع') : 'حُفظ، لكن تعذر الاتصال بالوكيل — سيُطبّق بالفحص القادم');
        }
        back();
    case 'quarantine':
        $paths = array_filter(array_map('strval', (array)($_POST['paths'] ?? [])));
        if ($S && $paths) { $d = quarantine_files($S, $paths, 'admin', trim((string)($_POST['reason'] ?? '')) ?: 'عزل يدوي'); back('تم عزل ' . count($d) . ' من ' . count($paths) . ' ملف', '?site=' . $sid . '&tab=files'); }
        back('لم تحدد ملفات');
    case 'restore': case 'qdel':
        $Q = q('SELECT * FROM gm_quarantine WHERE id=? AND state=?', [(int)($_POST['qid'] ?? 0), 'held'])->fetch();
        if ($Q && ($S = site((int)$Q['site_id'])) && ($j = agent_call($S, $act === 'restore' ? 'restore' : 'qdelete', ['q' => $Q['qname']])) && !empty($j['done'])) {
            q('UPDATE gm_quarantine SET state=? WHERE id=?', [$act === 'restore' ? 'restored' : 'deleted', $Q['id']]);
            act_log($S['id'], 'admin', $act, $Q['path'] . ' — sha256: ' . $Q['sha256']);
            back($act === 'restore' ? 'تم إرجاع الملف لمكانه' : 'تم حذف الملف نهائياً');
        }
        back('فشلت العملية (الملف غير موجود بالحجر أو المسار الأصلي مشغول)');
    case 'ignore':
        if ($S) {
            $ign = json_decode($S['scan_ignore'] ?? '', true) ?: []; $ign[] = (string)$_POST['path'];
            upd($sid, ['scan_ignore' => jenc(array_values(array_unique($ign)))]);
            $left = array_filter((json_decode($S['scan'] ?? '', true) ?: [])['hits'] ?? [], fn($x) => $x[1] && !in_array($x[0], $ign, true));
            if (!$left) close_silent($sid, ['malware']);
            act_log($sid, 'admin', 'ignore', 'تجاهل نتيجة الفحص: ' . $_POST['path']); back('تم — لن يُبلَّغ عن هذا الملف');
        }
        back();
    case 'block':
        $ip = trim((string)($_POST['ip'] ?? '')); $scope = (int)($_POST['scope'] ?? 0);
        if (!block_ip($scope, $ip, (int)($_POST['hours'] ?? 24), trim((string)($_POST['reason'] ?? '')) ?: 'حظر يدوي', 'admin')) back('IP غير صحيح أو ضمن القائمة المستثناة');
        push_all($scope); back("تم حظر $ip");
    case 'unblock':
        if ($B = q('SELECT * FROM gm_blocks WHERE id=?', [(int)($_POST['bid'] ?? 0)])->fetch()) {
            q('DELETE FROM gm_blocks WHERE id=?', [$B['id']]); act_log((int)$B['site_id'], 'admin', 'unblock', $B['ip']); push_all((int)$B['site_id']);
        }
        back('تم رفع الحظر');
    case 'settings':
        set_setting('tg_token', trim((string)$_POST['tg_token'])); set_setting('tg_chat', trim((string)$_POST['tg_chat']));
        back(tg("✅ <b>GHANI Monitor</b>\nتم ربط التنبيهات بنجاح") ? 'تم الحفظ ووصلتك رسالة تجربة على تيليگرام' : 'تم الحفظ لكن فشل إرسال رسالة التجربة — تأكد من التوكن و Chat ID');
    case 'policy':
        foreach (['rq_min', 'ip_max', 'login_max', 'atk_min', 'block_hours', 'keep_days'] as $k) set_setting($k, (string)max(1, (int)($_POST[$k] ?? 0)));
        foreach (['auto_block', 'auto_quarantine'] as $k) set_setting($k, empty($_POST[$k]) ? '0' : '1');
        set_setting('allow_ips', trim((string)($_POST['allow_ips'] ?? '')));
        act_log(0, 'admin', 'policy', 'تعديل سياسة الاستجابة: حظر تلقائي=' . setting('auto_block') . '، عزل تلقائي=' . setting('auto_quarantine'));
        push_all(); back('تم حفظ السياسة');
    case 'passwd':
        if (!password_verify((string)($_POST['old'] ?? ''), setting('admin_hash')) || strlen((string)($_POST['new'] ?? '')) < 10) back('كلمة المرور الحالية خاطئة أو الجديدة أقل من 10 أحرف');
        set_setting('admin_hash', password_hash($_POST['new'], PASSWORD_DEFAULT)); act_log(0, 'admin', 'passwd', 'تغيير كلمة المرور'); back('تم تغيير كلمة المرور');
    case 'run': back(run_checks() ? 'تم الفحص الآن' : 'يوجد فحص جارٍ حالياً');
}

/* ---------- التوجيه ---------- */
if (isset($_GET['report']) && ($s = site((int)$_GET['report']))) { view_report($s); exit; }
if (isset($_GET['ip']) && filter_var($_GET['ip'], FILTER_VALIDATE_IP)) { page_top('تحقيق في عنوان IP', true, 'attackers'); view_ip($_GET['ip']); page_end(); exit; }
if (isset($_GET['site']) && ($s = site((int)$_GET['site']))) {
    page_top('الأصل: ' . $s['name'], true, 'assets');
    if (isset($_GET['file']) || isset($_GET['q'])) view_file($s, (string)($_GET['file'] ?? ''), (string)($_GET['q'] ?? ''));
    else view_site($s);
    page_end(); exit;
}
$pages = ['alerts' => ['التنبيهات', 'view_alerts'], 'assets' => ['الأصول', 'view_assets'], 'attackers' => ['المهاجمون', 'view_attackers'],
          'quarantine' => ['الحجر', 'view_quarantine'], 'log' => ['سجل الإجراءات', 'view_log'], 'settings' => ['الإعدادات', 'view_settings']];
$v = (string)($_GET['v'] ?? '');
if (isset($pages[$v])) { page_top($pages[$v][0], true, $v); $pages[$v][1](); page_end(); exit; }
page_top('نظرة عامة', true, '', 120); view_overview(); page_end();
