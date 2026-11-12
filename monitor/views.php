<?php
/* ================= عناصر مشتركة ================= */
function csrf_in(): string {
    global $csrf;
    return '<input type="hidden" name="csrf" value="' . $csrf . '"><input type="hidden" name="ret" value="' . h('?' . ($_SERVER['QUERY_STRING'] ?? '')) . '">';
}
function f(string $act, string $label, array $fields = [], string $cls = 'g', string $confirm = ''): string {
    $o = '<form class="i" method="post"' . ($confirm ? ' onsubmit="return confirm(\'' . h($confirm) . '\')"' : '') . '>' . csrf_in();
    foreach ($fields as $k => $v) $o .= '<input type="hidden" name="' . h($k) . '" value="' . h($v) . '">';
    return $o . '<button class="' . $cls . '" name="act" value="' . h($act) . '">' . $label . '</button></form>';
}
function sev_badge(string $s): string {
    return '<span class="badge b-' . ['high' => 'danger', 'med' => 'warn', 'low' => 'wait'][$s] . '">' . ['high' => 'خطير', 'med' => 'متوسط', 'low' => 'منخفض'][$s] . '</span>';
}
function score_badge($sc): string {
    if ($sc === null) return '<span class="badge b-wait">—</span>';
    return '<span class="badge b-' . ($sc >= 80 ? 'ok' : ($sc >= 50 ? 'warn' : 'danger')) . '">' . (int)$sc . '/100</span>';
}
function ip_link(string $ip): string { return '<a class="ip" href="?ip=' . urlencode($ip) . '">' . h($ip) . '</a>'; }
function site_level(array $s, array $open): string {
    if ($s['lockdown']) return 'lock';
    $lv = $s['last_check'] ? 'ok' : 'wait';
    foreach ($open as $i) {
        $l = GM_TYPES[$i['type']][2];
        if ($l === 'danger' || ($l === 'down' && $lv !== 'danger') || ($l === 'warn' && ($lv === 'ok' || $lv === 'wait'))) $lv = $l;
    }
    return $lv;
}
const LV_NAME = ['ok' => 'سليم', 'warn' => 'تحذير', 'danger' => 'خطر', 'down' => 'متوقف', 'wait' => 'بانتظار الفحص', 'lock' => '🔒 مغلق'];

function page_top(string $title, bool $nav = true): void {
    // التواريخ والأوقات تُعرض من اليسار لليمين حتى لا تنقلب داخل النص العربي
    ob_start(fn($o) => preg_replace('~(?<![\w"=/-])(\d{4}-\d\d-\d\d(?: \d\d:\d\d(?::\d\d)?)?)(?![\w"-])~', '<bdi dir="ltr">$1</bdi>', $o));
    $flash = $_SESSION['flash'] ?? ''; unset($_SESSION['flash']); ?>
<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><meta name="referrer" content="no-referrer"><title><?= h($title) ?></title><style>
:root{--bg:#0b1416;--card:#122024;--line:#1f3338;--tx:#e6f1f2;--mut:#8aa4a8;--ac:#19b8b0;--ok:#2ecc71;--warn:#f1c40f;--bad:#ff4d4f;--down:#b0413e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.6 system-ui,'Segoe UI',Tahoma,sans-serif}
a{color:var(--ac)}.wrap{max-width:1040px;margin:auto;padding:14px}h1{font-size:19px;margin:0}h2{font-size:15px;margin:22px 0 8px;color:var(--mut)}
header{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:12px}
nav{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px;margin-bottom:11px}
.row{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:center}
.badge{padding:2px 11px;border-radius:99px;font-size:12.5px;font-weight:700;color:#06100f;white-space:nowrap}
.b-ok{background:var(--ok)}.b-warn{background:var(--warn)}.b-danger{background:var(--bad);color:#fff}.b-down{background:var(--down);color:#fff}.b-wait{background:#567;color:#fff}.b-lock{background:#8e44ad;color:#fff}
.meta{color:var(--mut);font-size:13px;display:flex;gap:12px;flex-wrap:wrap;margin-top:6px}
.iss{border-inline-start:3px solid var(--bad);background:#1a1214;padding:8px 10px;border-radius:6px;margin-top:8px;white-space:pre-wrap;word-break:break-word;font-size:13px}
.iss.warn{border-color:var(--warn);background:#1a1810}.iss.low{border-color:#567;background:#121a1d}
input,select,button,textarea{font:inherit;border-radius:8px;border:1px solid var(--line);background:#0d181b;color:var(--tx);padding:7px 10px}
input[type=text],input[type=url],input[type=password],select,textarea{width:100%}label{display:block;margin:8px 0 3px;color:var(--mut);font-size:13px}
button,.btn{cursor:pointer;background:var(--ac);border:0;color:#04201e;font-weight:700;text-decoration:none;display:inline-block;padding:6px 11px;border-radius:8px;font-size:13px}
.btn.g,button.g{background:#24383d;color:var(--tx)}button.r,.btn.r{background:#4a1f21;color:#ffb3b3}button.p{background:#8e44ad;color:#fff}
form.i{display:inline}.acts{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;align-items:center}
.flash{background:#103532;border:1px solid var(--ac);padding:10px;border-radius:8px;margin-bottom:12px}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:5px 6px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top}th{color:var(--mut);font-weight:600}
details summary{cursor:pointer;font-weight:700}details[open] summary{margin-bottom:8px}
.sum{display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:8px;margin-bottom:12px}
.sum div{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:9px;text-align:center;font-size:13px}.sum b{display:block;font-size:21px}
code,.ip{background:#0d181b;padding:1px 6px;border-radius:5px;direction:ltr;display:inline-block;word-break:break-all;font-family:ui-monospace,Consolas,monospace;font-size:12.5px;text-decoration:none}
pre.src{direction:ltr;text-align:left;background:#081012;border:1px solid var(--line);border-radius:8px;padding:8px;overflow:auto;font:12px/1.5 ui-monospace,Consolas,monospace;max-height:70vh;margin:0}
pre.src span{display:block;white-space:pre}pre.src span.hot{background:#4a1f21}pre.src i{color:#567;font-style:normal;user-select:none;display:inline-block;width:42px}
.ov{overflow:auto}.tl td:first-child{white-space:nowrap;color:var(--mut)}
</style></head><body><div class="wrap">
<?php if ($nav): ?><header><h1><a href="?" style="color:inherit;text-decoration:none">🛡️ GHANI Monitor</a></h1><nav>
<a class="btn g" href="?">المواقع</a><a class="btn g" href="?v=log">السجل</a><a class="btn g" href="?v=settings">الإعدادات</a>
<?= f('run', 'افحص الآن', [], '') ?><?= f('logout', 'خروج') ?></nav></header><?php endif ?>
<?php if ($flash): ?><div class="flash"><?= h($flash) ?></div><?php endif;
}
function page_end(): void { echo '</div></body></html>'; ob_end_flush(); }

/* ================= الرئيسية ================= */
function view_overview(): void {
    $sites = q('SELECT * FROM gm_sites ORDER BY id')->fetchAll();
    $open = [];
    foreach (q('SELECT * FROM gm_issues WHERE closed_at IS NULL ORDER BY id')->fetchAll() as $i) $open[$i['site_id']][] = $i;
    $cnt = ['ok' => 0, 'warn' => 0, 'danger' => 0, 'down' => 0];
    foreach ($sites as &$s) { $s['lv'] = site_level($s, $open[$s['id']] ?? []); if (isset($cnt[$s['lv']])) $cnt[$s['lv']]++; }
    unset($s);
    $atk = (int)q("SELECT COUNT(*) FROM gm_requests WHERE tag<>'' AND at>?", [ago(86400)])->fetchColumn();
    $blk = (int)q('SELECT COUNT(*) FROM gm_blocks WHERE expires IS NULL OR expires>?', [now()])->fetchColumn();
    $qn = (int)q("SELECT COUNT(*) FROM gm_quarantine WHERE state='held'")->fetchColumn();
    $last = setting('last_cron'); $stale = !$last || strtotime($last) < time() - 900; ?>
<meta http-equiv="refresh" content="120">
<?php if ($stale): ?><div class="iss warn">⚠️ الفحص الدوري لا يعمل (آخر تشغيل: <?= h($last ?: 'لم يعمل بعد') ?>) — تأكد من إعداد Cron كل 5 دقائق.</div><br><?php endif ?>
<div class="sum"><div><b style="color:var(--ok)"><?= $cnt['ok'] ?></b>سليم</div><div><b style="color:var(--warn)"><?= $cnt['warn'] ?></b>تحذير</div>
<div><b style="color:var(--bad)"><?= $cnt['danger'] ?></b>خطر</div><div><b style="color:#e08a87"><?= $cnt['down'] ?></b>متوقف</div>
<div><b><?= $atk ?></b>طلب هجومي / 24س</div><div><b><?= $blk ?></b>IP محظور</div><div><b><?= $qn ?></b>ملف بالحجر</div></div>
<div class="meta" style="margin-bottom:10px">آخر فحص دوري: <?= h($last ?: '—') ?></div>
<?php foreach ($sites as $s): $tr = !empty($s['traffic_last']) ? json_decode($s['traffic_last'], true) : null; ?>
<div class="card"><div class="row"><div><a href="?site=<?= $s['id'] ?>"><b><?= h($s['name']) ?></b></a> <span class="meta" style="display:inline"><?= h(host_of($s['url'])) ?></span></div>
  <div><?= score_badge($s['score']) ?> <span class="badge b-<?= $s['lv'] ?>"><?= LV_NAME[$s['lv']] ?></span></div></div>
  <div class="meta"><span>HTTP <?= h($s['http_code'] ?? '—') ?> · <?= h($s['resp_ms'] ?? '—') ?>ms</span>
    <span><?= $s['ssh_host'] ? 'SSH' : 'الوكيل' ?>: <?= !has_agent($s) ? 'غير مفعّل' : ($s['agent_ok'] === null ? '⏳' : ($s['agent_ok'] ? '✅' : '❌')) ?></span>
    <span>الطلبات: <?= $tr ? (int)$tr['total'] . '/5د' : '—' ?></span><span>آخر فحص: <?= h($s['last_check'] ?? '—') ?></span></div>
  <?php foreach ($open[$s['id']] ?? [] as $i): ?><div class="iss <?= GM_TYPES[$i['type']][2] === 'warn' ? 'warn' : '' ?>"><b><?= GM_TYPES[$i['type']][0] . ' ' . GM_TYPES[$i['type']][1] ?></b> <small>(منذ <?= h($i['opened_at']) ?>)</small></div><?php endforeach ?>
</div>
<?php endforeach ?>
<?php if (!$sites): ?><div class="card">لا توجد مواقع بعد — أضف أول موقع من الأسفل.</div><?php endif ?>

<div class="card"><details <?= $sites ? '' : 'open' ?>><summary>➕ إضافة موقع</summary>
<form method="post"><?= csrf_in() ?><input type="hidden" name="act" value="add">
<label>اسم الموقع</label><input type="text" name="name" placeholder="مثال: غني كود">
<label>الرابط</label><input type="url" name="url" placeholder="https://example.com" required dir="ltr">
<label>كلمة ثابتة يجب أن تظهر بالصفحة (اختياري)</label><input type="text" name="keyword">
<label><input type="checkbox" name="agent" checked> ملف الوكيل/الحارس gm-agent.php (ضروري لعدّ الطلبات، كشف الهجمات، الحظر، والإغلاق)</label>
<details style="margin:8px 0"><summary>🔌 اتصال SSH (اختياري — فحص الملفات والعزل بدون رفع أي ملف)</summary>
<label>الخادم (IP أو اسم)</label><input type="text" name="ssh_host" dir="ltr" placeholder="123.45.67.89">
<label>المنفذ (هوستنجر المشترك عادةً 65002)</label><input type="text" name="ssh_port" dir="ltr" value="65002">
<label>اسم المستخدم</label><input type="text" name="ssh_user" dir="ltr" placeholder="u123456789">
<label>المسار الكامل للمجلد العام (public_html أو public)</label><input type="text" name="ssh_path" dir="ltr" placeholder="/home/u123456789/domains/example.com/public_html">
<p class="meta">أضف المفتاح العام للمراقب (من الإعدادات) إلى SSH Keys في لوحة الاستضافة أولاً.</p></details>
<label><input type="checkbox" name="laravel"> الموقع Laravel (الوكيل داخل public ويغطي المشروع كله)</label>
<label><input type="checkbox" name="cf"> الموقع خلف Cloudflare (يقرأ IP الزائر الحقيقي من ترويسة Cloudflare)</label>
<label><input type="checkbox" name="deface" checked> فحص عبارات التشويه داخل المحتوى (ألغِه لمواقع تكتب عن الاختراق)</label>
<p><button>إضافة</button></p></form></details></div>

<?php $top = q("SELECT ip, COUNT(*) c, COUNT(DISTINCT site_id) s, MAX(at) l FROM gm_requests WHERE tag<>'' AND at>? GROUP BY ip ORDER BY c DESC LIMIT 10", [ago(86400)])->fetchAll();
if ($top): ?><h2>أكثر المهاجمين — آخر 24 ساعة</h2><div class="card ov"><table><tr><th>IP</th><th>طلبات هجومية</th><th>مواقع</th><th>آخر نشاط</th></tr>
<?php foreach ($top as $t): ?><tr><td><?= ip_link($t['ip']) ?></td><td><?= (int)$t['c'] ?></td><td><?= (int)$t['s'] ?></td><td><?= h($t['l']) ?></td></tr><?php endforeach ?></table></div><?php endif ?>

<h2>آخر الأحداث</h2><div class="card ov"><table><tr><th>الموقع</th><th>الحدث</th><th>بدأ</th><th>انتهى</th></tr>
<?php foreach (q('SELECT i.*, s.name FROM gm_issues i LEFT JOIN gm_sites s ON s.id=i.site_id ORDER BY i.id DESC LIMIT 40')->fetchAll() as $i): ?>
<tr><td><a href="?site=<?= (int)$i['site_id'] ?>"><?= h($i['name']) ?></a></td><td><?= GM_TYPES[$i['type']][0] . ' ' . GM_TYPES[$i['type']][1] ?></td><td><?= h($i['opened_at']) ?></td><td><?= h($i['closed_at'] ?? 'مفتوح') ?></td></tr>
<?php endforeach ?></table></div><?php
}

/* ================= صفحة الموقع ================= */
function view_site(array $s): void {
    $id = (int)$s['id'];
    $open = q('SELECT * FROM gm_issues WHERE site_id=? AND closed_at IS NULL ORDER BY id', [$id])->fetchAll();
    $lv = site_level($s, $open);
    $diff = $s['files_diff'] ? json_decode($s['files_diff'], true) : null;
    $tr = !empty($s['traffic_last']) ? json_decode($s['traffic_last'], true) : null;
    $au = json_decode($s['audit'] ?? '', true) ?: null;
    $sc = json_decode($s['scan'] ?? '', true) ?: null;
    $ign = json_decode($s['scan_ignore'] ?? '', true) ?: [];
    $ssl = $s['ssl_expires'] ? (int)floor((strtotime($s['ssl_expires']) - time()) / 86400) : null; ?>
<div class="card"><div class="row"><div><b style="font-size:17px"><?= h($s['name']) ?></b> — <a href="<?= h($s['url']) ?>" target="_blank" rel="noopener noreferrer"><?= h(host_of($s['url'])) ?></a></div>
  <div><?= score_badge($s['score']) ?> <span class="badge b-<?= $lv ?>"><?= LV_NAME[$lv] ?></span></div></div>
  <div class="meta"><span>HTTP: <?= h($s['http_code'] ?? '—') ?></span><span>الاستجابة: <?= h($s['resp_ms'] ?? '—') ?>ms</span><span>SSL: <?= $ssl === null ? '—' : $ssl . ' يوم' ?></span>
    <span>DNS: <?= h($s['dns_base'] ?? '—') ?></span>
    <span><?= $s['ssh_host'] ? 'SSH (' . h($s['ssh_user'] . '@' . $s['ssh_host']) . ')' : 'الوكيل' ?>: <?= !has_agent($s) ? 'غير مفعّل' : ($s['agent_ok'] === null ? ($s['ssh_host'] ? '⏳ بانتظار أول اتصال' : '⏳ بانتظار رفع الملف') : ($s['agent_ok'] ? '✅ ' . (int)$s['files_count'] . ' ملف مراقَب' : '❌ لا يستجيب')) ?></span>
    <span>الحارس: <?= $tr ? '✅ ' . (int)$tr['total'] . ' طلب/5د' . (!empty($tr['blocked']) ? ' · ' . (int)$tr['blocked'] . ' محجوب' : '') : 'غير مربوط' ?></span>
    <span>آخر فحص: <?= h($s['last_check'] ?? '—') ?></span></div>
  <?php foreach ($open as $i): ?><div class="iss <?= GM_TYPES[$i['type']][2] === 'warn' ? 'warn' : '' ?>"><b><?= GM_TYPES[$i['type']][0] . ' ' . GM_TYPES[$i['type']][1] ?></b> <small>(منذ <?= h($i['opened_at']) ?>)</small>
<?= h($i['message']) ?></div><?php endforeach ?>
  <div class="acts">
    <?php if ($s['ssh_host']): ?><?= f('sshtest', '🔌 اختبار SSH', ['id' => $id], '') ?><?php endif ?>
    <?php if ($s['agent_url']): ?><a class="btn<?= $s['ssh_host'] ? ' g' : '' ?>" href="?agent=<?= $id ?>">⬇️ تنزيل <?= $s['ssh_host'] ? 'الحارس' : 'الوكيل' ?></a><?php endif ?>
    <?php if (has_agent($s)): ?><?= f('scan', '🔬 فحص عميق', ['id' => $id]) ?><?php endif ?>
    <?= f('audit', '🧱 تدقيق أمني', ['id' => $id]) ?>
    <a class="btn g" href="?report=<?= $id ?>" target="_blank">📄 تقرير الحادث</a>
    <?php if ($s['agent_url']): ?><?= $s['lockdown'] ? f('unlock', '🔓 فتح الموقع', ['id' => $id], 'p') : f('lock', '🔒 إغلاق طارئ', ['id' => $id], 'p', 'سيُغلق الموقع أمام كل الزوار عدا الـ IPs المستثناة. متأكد؟') ?><?php endif ?>
    <?= f('ok_page', 'اعتماد الصفحة/DNS', ['id' => $id]) ?>
    <?= f('del', 'حذف', ['id' => $id], 'r', 'حذف الموقع وكل سجلاته من المراقبة؟') ?>
  </div>
</div>

<?php if ($diff): $all = ['added' => '➕ جديد', 'mod' => '✏️ معدّل', 'removed' => '➖ محذوف']; ?>
<div class="card"><details open><summary>📁 تغييرات الملفات غير المعتمدة</summary>
<form method="post" onsubmit="return confirm('عزل الملفات المحددة؟ ستُنقل إلى الحجر ويمكن إرجاعها.')"><?= csrf_in() ?><input type="hidden" name="id" value="<?= $id ?>">
<div class="ov"><table><?php foreach ($all as $k => $lbl) foreach (array_slice($diff[$k], 0, 150) as $p): $hot = in_array($p, $diff['strong'] ?? [], true); ?>
  <tr><td><?php if ($k !== 'removed'): ?><input type="checkbox" name="paths[]" value="<?= h($p) ?>" <?= $hot ? 'checked' : '' ?>><?php endif ?></td>
  <td style="white-space:nowrap"><?= $lbl ?></td><td><code><?= h($p) ?></code><?= isset($diff['sus'][$p]) ? '<br>' . ($hot ? '☠️ ' : '⚠️ ') . h(implode('، ', $diff['sus'][$p])) : '' ?></td>
  <td><?php if ($k !== 'removed'): ?><a href="?site=<?= $id ?>&file=<?= urlencode($p) ?>">عرض</a><?php endif ?></td></tr>
<?php endforeach ?></table></div>
<div class="acts"><button class="r" name="act" value="quarantine">🧹 عزل المحدد</button></div></form>
<div class="acts"><?= f('ok_files', '✅ كل التغييرات مني — اعتماد', ['id' => $id], 'g', 'متأكد أن كل التغييرات منك؟ ستُعتمد الملفات الحالية كأساس.') ?></div>
<p class="meta">الملفات المعدّلة لا يمكن إرجاع نسختها الأصلية من هنا — استرجعها من نسخة احتياطية أو أعد رفعها من المصدر.</p>
</details></div><?php endif ?>

<?php if ($sc): $hits = array_values(array_filter($sc['hits'], fn($x) => !in_array($x[0], $ign, true))); ?>
<div class="card"><details <?= array_filter($hits, fn($x) => $x[1]) ? 'open' : '' ?>><summary>🔬 الفحص العميق — <?= empty($sc['done']) ? 'جارٍ…' : 'فُحص ' . (int)$sc['scanned'] . ' ملف' ?> · <?= count($hits) ?> نتيجة <small>(<?= h($sc['at'] ?? '') ?>)</small></summary>
<?php if (!$hits): ?><p>لا توجد نتائج مشبوهة ✅</p><?php else: ?><div class="ov"><table>
<?php foreach (array_slice($hits, 0, 200) as $x): ?><tr><td><?= $x[1] ? '<span class="badge b-danger">توقيع خبيث</span>' : '<span class="badge b-warn">مؤشر ضعيف</span>' ?></td>
  <td><code><?= h($x[0]) ?></code><br><?= h(implode('، ', array_merge($x[1], $x[2]))) ?></td>
  <td style="white-space:nowrap"><a class="btn g" href="?site=<?= $id ?>&file=<?= urlencode($x[0]) ?>">عرض</a>
  <?= f('quarantine', 'عزل', ['id' => $id, 'paths[]' => $x[0], 'reason' => 'الفحص العميق: ' . implode('، ', array_merge($x[1], $x[2]))], 'r', 'عزل هذا الملف؟') ?>
  <?= f('ignore', 'تجاهل', ['id' => $id, 'path' => $x[0]]) ?></td></tr><?php endforeach ?></table></div>
<p class="meta">«مؤشر ضعيف» يظهر كثيراً في مكتبات سليمة — اعرض الملف قبل العزل.</p><?php endif ?></details></div><?php endif ?>

<?php if ($au): ?><div class="card"><details><summary>🧱 التدقيق الأمني — <?= count($au['findings']) ?> ملاحظة · الدرجة <?= (int)$s['score'] ?>/100 <small>(<?= h($s['audit_at']) ?>)</small></summary>
<?php if (!empty($au['info'])): ?><div class="meta">PHP <?= h($au['info']['php']) ?> · <?= h($au['info']['server']) ?> · <?= (int)$au['info']['files'] ?> ملف · <?= (int)$au['info']['recent48h'] ?> ملف تغيّر خلال 48 ساعة</div><?php endif ?>
<?php foreach ($au['findings'] as $x): ?><div class="iss <?= ['high' => '', 'med' => 'warn', 'low' => 'low'][$x[0]] ?>"><?= sev_badge($x[0]) ?> <b><?= h($x[1]) ?></b>
<?= h($x[2]) ?></div><?php endforeach ?>
<?php if (!$au['findings']): ?><p>لا توجد ملاحظات ✅</p><?php endif ?></details></div><?php endif ?>

<?php $atk = q("SELECT ip, tag, COUNT(*) c, MAX(at) l FROM gm_requests WHERE site_id=? AND tag<>'' AND at>? GROUP BY ip, tag ORDER BY c DESC LIMIT 30", [$id, ago(86400)])->fetchAll();
if ($tr || $atk): ?><div class="card"><details><summary>🎯 الطلبات والهجمات</summary>
<?php if ($atk): ?><b>هجمات آخر 24 ساعة</b><div class="ov"><table><tr><th>IP</th><th>النوع</th><th>العدد</th><th>آخر مرة</th><th></th></tr>
<?php foreach ($atk as $a): ?><tr><td><?= ip_link($a['ip']) ?></td><td><?= h(GM_TAGS[$a['tag']] ?? $a['tag']) ?></td><td><?= (int)$a['c'] ?></td><td><?= h($a['l']) ?></td>
<td><?= f('block', 'حظر 24س', ['ip' => $a['ip'], 'scope' => $id, 'hours' => 24, 'reason' => 'هجوم: ' . (GM_TAGS[$a['tag']] ?? $a['tag'])], 'r') ?></td></tr><?php endforeach ?></table></div><?php endif ?>
<?php if ($tr && $tr['total']): ?><br><b>آخر 5 دقائق — <?= (int)$tr['uniq'] ?> IP</b><div class="ov"><table>
<?php foreach ($tr['ips'] as $k => $c): ?><tr><td>IP</td><td><?= ip_link((string)$k) ?></td><td><?= (int)$c ?></td></tr><?php endforeach ?>
<?php foreach ($tr['paths'] as $k => $c): ?><tr><td>مسار</td><td><code><?= h($k) ?></code></td><td><?= (int)$c ?></td></tr><?php endforeach ?></table></div><?php endif ?>
</details></div><?php endif ?>

<?php $qs = q('SELECT * FROM gm_quarantine WHERE site_id=? ORDER BY id DESC LIMIT 100', [$id])->fetchAll();
if ($qs): ?><div class="card"><details><summary>🧹 الحجر — <?= count(array_filter($qs, fn($x) => $x['state'] === 'held')) ?> ملف محجوز</summary><div class="ov"><table>
<tr><th>الملف</th><th>السبب</th><th>وقت العزل</th><th>الحالة</th></tr>
<?php foreach ($qs as $x): ?><tr><td><code><?= h($x['path']) ?></code><br><small>sha256: <?= h($x['sha256']) ?></small></td><td><?= h($x['reason']) ?> <small>(<?= h($x['actor']) ?>)</small></td><td><?= h($x['at']) ?></td>
<td style="white-space:nowrap"><?php if ($x['state'] === 'held'): ?><a class="btn g" href="?site=<?= $id ?>&q=<?= h($x['qname']) ?>">عرض</a>
<?= f('restore', 'إرجاع', ['qid' => $x['id']], 'g', 'إرجاع الملف لمكانه الأصلي؟') ?><?= f('qdel', 'حذف نهائي', ['qid' => $x['id']], 'r', 'حذف نهائي؟ لا يمكن التراجع، وتفقد الدليل.') ?>
<?php else: ?><?= $x['state'] === 'restored' ? 'أُرجع' : 'حُذف' ?><?php endif ?></td></tr><?php endforeach ?></table></div></details></div><?php endif ?>

<?php if (has_agent($s)): $hrs = (int)($_GET['hours'] ?? 0); ?><div class="card"><details <?= $hrs ? 'open' : '' ?>><summary>🕵️ تحقيق: الملفات التي تغيّرت مؤخراً (حسب ctime)</summary>
<form method="get" class="acts"><input type="hidden" name="site" value="<?= $id ?>">
<select name="hours" style="width:auto"><?php foreach ([1 => 'آخر ساعة', 6 => 'آخر 6 ساعات', 24 => 'آخر 24 ساعة', 72 => 'آخر 3 أيام', 168 => 'آخر أسبوع', 720 => 'آخر 30 يوم'] as $k => $v): ?><option value="<?= $k ?>" <?= $hrs === $k ? 'selected' : '' ?>><?= $v ?></option><?php endforeach ?></select><button>بحث</button></form>
<?php if ($hrs): $t = agent_call($s, 'timeline', ['hours' => $hrs]);
  if (!$t): ?><p>تعذر الاتصال بالموقع</p><?php else: ?><p class="meta"><?= (int)$t['count'] ?> ملف (كل الأنواع). ctime لا يتغيّر بأمر touch، فاختلافه عن mtime مؤشر على تزوير التاريخ.</p>
<div class="ov"><table><tr><th>الملف</th><th>ctime</th><th>mtime</th><th>الحجم</th><th>صلاحيات</th></tr>
<?php foreach ($t['files'] as $x): $fake = abs($x[3] - $x[2]) > 86400; ?><tr><td><a href="?site=<?= $id ?>&file=<?= urlencode($x[0]) ?>"><code><?= h($x[0]) ?></code></a></td>
<td><?= date('m-d H:i:s', $x[3]) ?></td><td <?= $fake ? 'style="color:var(--warn)"' : '' ?>><?= date('Y-m-d H:i', $x[2]) ?><?= $fake ? ' ⚠️' : '' ?></td><td><?= (int)$x[1] ?></td><td><?= h($x[4]) ?></td></tr><?php endforeach ?></table></div>
<?php endif; endif ?></details></div><?php endif ?>

<div class="card"><details><summary>⏱️ الخط الزمني للموقع</summary><div class="ov"><table class="tl">
<?php $ev = [];
foreach (q('SELECT * FROM gm_issues WHERE site_id=? ORDER BY id DESC LIMIT 80', [$id]) as $i) {
    $ev[] = [$i['opened_at'], GM_TYPES[$i['type']][0] . ' بدأ: ' . GM_TYPES[$i['type']][1]];
    if ($i['closed_at']) $ev[] = [$i['closed_at'], '✅ انتهى: ' . GM_TYPES[$i['type']][1]];
}
foreach (q('SELECT * FROM gm_filelog WHERE site_id=? ORDER BY id DESC LIMIT 120', [$id]) as $x) $ev[] = [$x['at'], ['added' => '➕', 'mod' => '✏️', 'removed' => '➖'][$x['chg']] . ' ' . $x['path'] . ($x['sus'] ? ' ☠️ ' . $x['sus'] : '')];
foreach (q('SELECT * FROM gm_actions WHERE site_id=? ORDER BY id DESC LIMIT 80', [$id]) as $x) $ev[] = [$x['at'], '🛠️ [' . $x['actor'] . '] ' . $x['action'] . ': ' . $x['detail']];
usort($ev, fn($a, $b) => strcmp($b[0], $a[0]));
foreach (array_slice($ev, 0, 200) as $e): ?><tr><td><?= h($e[0]) ?></td><td><?= h($e[1]) ?></td></tr><?php endforeach ?>
</table></div></details></div>

<?php if ($s['agent_url']): ?><div class="card"><details><summary>🔗 ربط الحارس (عدّ الطلبات، الحظر، الإغلاق الطارئ)</summary>
<p>بعد رفع <code>gm-agent.php</code>:</p>
<p><b>Laravel:</b> أضف بعد <code>&lt;?php</code> في <code>public/index.php</code>:<br><code>require_once __DIR__.'/gm-agent.php';</code></p>
<p><b>PHP عادي:</b> نفس السطر أعلى <code>index.php</code>، أو ليغطي كل الصفحات أضف في <code>.user.ini</code>:<br><code>auto_prepend_file = "/المسار/الكامل/public_html/gm-agent.php"</code></p>
<p class="meta">بعدها يصلك تنبيه تغيير ملفات مرة واحدة — اعتمده.</p></details></div><?php endif;
}

/* ================= عارض الملفات ================= */
function view_file(array $s, string $path, string $qn): void {
    $id = (int)$s['id'];
    $j = agent_call($s, 'get', $qn !== '' ? ['q' => $qn] : ['path' => $path]);
    echo '<p><a href="?site=' . $id . '">→ رجوع إلى ' . h($s['name']) . '</a></p>';
    if (!$j || empty($j['found'])) { echo '<div class="card">تعذر قراءة الملف (غير موجود، أو نوعه غير مسموح بعرضه، أو الوكيل لا يستجيب).</div>'; return; }
    $src = (string)base64_decode($j['b64']);
    if (!mb_check_encoding($src, 'UTF-8')) $src = preg_replace('~[^\x09\x0A\x20-\x7E]~', '·', $src);
    $Q = $qn !== '' ? q('SELECT * FROM gm_quarantine WHERE site_id=? AND qname=?', [$id, $qn])->fetch() : null; ?>
<div class="card"><b><?= $qn !== '' ? '🧹 ملف بالحجر: ' : '' ?><code><?= h($j['path']) ?></code></b>
<div class="ov"><table>
<tr><td>الحجم</td><td><?= (int)$j['size'] ?> بايت</td></tr><tr><td>آخر تعديل (mtime)</td><td><?= date('Y-m-d H:i:s', $j['mtime']) ?></td></tr>
<tr><td>تغيير inode (ctime)</td><td><?= date('Y-m-d H:i:s', $j['ctime']) ?></td></tr><tr><td>الصلاحيات</td><td><?= h($j['perms']) ?></td></tr>
<tr><td>MD5</td><td><code><?= h($j['md5']) ?></code></td></tr><tr><td>SHA-256</td><td><code><?= h($j['sha256']) ?></code> <a href="https://www.virustotal.com/gui/search/<?= h($j['sha256']) ?>" target="_blank" rel="noopener noreferrer">بحث VirusTotal</a></td></tr>
</table></div>
<?php foreach ($j['hits']['s'] as $x): ?><div class="iss">☠️ <?= h($x) ?></div><?php endforeach ?>
<?php foreach ($j['hits']['w'] as $x): ?><div class="iss warn">⚠️ <?= h($x) ?></div><?php endforeach ?>
<div class="acts"><?php if ($qn === ''): ?><?= f('quarantine', '🧹 عزل هذا الملف', ['id' => $id, 'paths[]' => $j['path'], 'reason' => 'عزل يدوي من عارض الملفات'], 'r', 'عزل هذا الملف؟') ?>
<?php elseif ($Q && $Q['state'] === 'held'): ?><?= f('restore', 'إرجاع', ['qid' => $Q['id']], 'g', 'إرجاع الملف لمكانه الأصلي؟') ?><?= f('qdel', 'حذف نهائي', ['qid' => $Q['id']], 'r', 'حذف نهائي؟') ?><?php endif ?></div></div>
<pre class="src"><?php $re = '~eval\s*\(|base64_decode|gzinflate|gzuncompress|str_rot13|shell_exec|passthru|system\s*\(|proc_open|popen|assert\s*\(|\$_(POST|GET|REQUEST|COOKIE)|move_uploaded_file|auto_prepend_file~i';
foreach (explode("\n", $src) as $n => $line) echo '<span' . (preg_match($re, $line) ? ' class="hot"' : '') . '><i>' . ($n + 1) . '</i>' . h(mb_substr($line, 0, 2000)) . "</span>";
?></pre><?php if ($j['size'] > 204800): ?><p class="meta">عُرض أول 200KB فقط.</p><?php endif;
}

/* ================= تحقيق IP ================= */
function view_ip(string $ip): void {
    $sites = []; foreach (q('SELECT id, name FROM gm_sites ORDER BY id') as $x) $sites[$x['id']] = $x['name'];
    $st = q('SELECT COUNT(*) c, MIN(at) f, MAX(at) l FROM gm_requests WHERE ip=?', [$ip])->fetch();
    $bySite = q("SELECT site_id, COUNT(*) c, SUM(CASE WHEN tag<>'' THEN 1 ELSE 0 END) a FROM gm_requests WHERE ip=? GROUP BY site_id ORDER BY c DESC", [$ip])->fetchAll();
    $byTag = q("SELECT tag, COUNT(*) c FROM gm_requests WHERE ip=? AND tag<>'' GROUP BY tag ORDER BY c DESC", [$ip])->fetchAll();
    $uas = q('SELECT ua, COUNT(*) c FROM gm_requests WHERE ip=? GROUP BY ua ORDER BY c DESC LIMIT 5', [$ip])->fetchAll();
    $blocks = q('SELECT * FROM gm_blocks WHERE ip=? AND (expires IS NULL OR expires>?)', [$ip, now()])->fetchAll(); ?>
<div class="card"><div class="row"><b style="font-size:17px">🕵️ <code><?= h($ip) ?></code></b>
<div><a class="btn g" href="https://www.abuseipdb.com/check/<?= h($ip) ?>" target="_blank" rel="noopener noreferrer">AbuseIPDB</a> <a class="btn g" href="https://ipinfo.io/<?= h($ip) ?>" target="_blank" rel="noopener noreferrer">ipinfo</a></div></div>
<div class="meta"><span>طلبات مسجّلة: <?= (int)$st['c'] ?></span><span>أول ظهور: <?= h($st['f'] ?? '—') ?></span><span>آخر ظهور: <?= h($st['l'] ?? '—') ?></span></div>
<?php foreach ($blocks as $b): ?><div class="iss">⛔ محظور على <?= $b['site_id'] ? h($sites[$b['site_id']] ?? '?') : 'كل المواقع' ?> — <?= h($b['reason']) ?> — حتى <?= h($b['expires'] ?? 'دائم') ?> <?= f('unblock', 'رفع الحظر', ['bid' => $b['id']]) ?></div><?php endforeach ?>
<form method="post" class="acts"><?= csrf_in() ?><input type="hidden" name="ip" value="<?= h($ip) ?>">
<select name="scope" style="width:auto"><option value="0">كل المواقع</option><?php foreach ($sites as $k => $v): ?><option value="<?= $k ?>"><?= h($v) ?></option><?php endforeach ?></select>
<select name="hours" style="width:auto"><option value="1">ساعة</option><option value="24" selected>24 ساعة</option><option value="168">أسبوع</option><option value="720">30 يوم</option><option value="0">دائم</option></select>
<input type="text" name="reason" placeholder="السبب" style="width:auto;flex:1;min-width:120px"><button class="r" name="act" value="block">⛔ حظر</button></form></div>
<?php if ($bySite): ?><div class="card ov"><table><tr><th>الموقع</th><th>طلبات</th><th>هجومية</th></tr>
<?php foreach ($bySite as $x): ?><tr><td><a href="?site=<?= (int)$x['site_id'] ?>"><?= h($sites[$x['site_id']] ?? '?') ?></a></td><td><?= (int)$x['c'] ?></td><td><?= (int)$x['a'] ?></td></tr><?php endforeach ?>
<?php foreach ($byTag as $x): ?><tr><td>نوع الهجوم</td><td><?= h(GM_TAGS[$x['tag']] ?? $x['tag']) ?></td><td><?= (int)$x['c'] ?></td></tr><?php endforeach ?>
<?php foreach ($uas as $x): ?><tr><td>User-Agent</td><td><code><?= h($x['ua'] ?: '(فارغ)') ?></code></td><td><?= (int)$x['c'] ?></td></tr><?php endforeach ?></table></div><?php endif ?>
<h2>آخر 300 طلب مسجّل</h2><div class="card ov"><table><tr><th>الوقت</th><th>الموقع</th><th></th><th>الطلب</th><th>التصنيف</th></tr>
<?php foreach (q('SELECT * FROM gm_requests WHERE ip=? ORDER BY at DESC, id DESC LIMIT 300', [$ip]) as $r): ?>
<tr><td style="white-space:nowrap"><?= h($r['at']) ?></td><td><?= h($sites[$r['site_id']] ?? '?') ?></td><td><?= h($r['method']) ?></td><td><code><?= h($r['path']) ?></code></td><td><?= $r['tag'] ? '<span class="badge b-danger">' . h(GM_TAGS[$r['tag']] ?? $r['tag']) . '</span>' : '' ?></td></tr>
<?php endforeach ?></table></div>
<p class="meta">السجل يحفظ كل الطلبات الهجومية وغير GET، وعيّنة من الطلبات العادية، لمدة <?= (int)setting('keep_days', 7) ?> أيام.</p><?php
}

/* ================= الإعدادات والسجل ================= */
function view_settings(): void { $v = fn($k, $d) => (int)setting($k, $d); ?>
<div class="card"><details <?= setting('tg_token') ? '' : 'open' ?>><summary>🔔 تيليگرام</summary>
<form method="post"><?= csrf_in() ?><input type="hidden" name="act" value="settings">
<label>Bot Token (من @BotFather)</label><input type="text" name="tg_token" value="<?= h(setting('tg_token', '')) ?>" dir="ltr">
<label>Chat ID (رقمك أو رقم الكروب)</label><input type="text" name="tg_chat" value="<?= h(setting('tg_chat', '')) ?>" dir="ltr">
<p><button>حفظ وإرسال تجربة</button></p></form></details></div>

<div class="card"><details open><summary>⚙️ سياسة الكشف والاستجابة</summary>
<form method="post"><?= csrf_in() ?><input type="hidden" name="act" value="policy">
<label><input type="checkbox" name="auto_block" <?= setting('auto_block') === '1' ? 'checked' : '' ?>> حظر تلقائي لأي IP يهاجم أو يجرّب كلمات السر أو يغرق الموقع</label>
<label><input type="checkbox" name="auto_quarantine" <?= setting('auto_quarantine') === '1' ? 'checked' : '' ?>> عزل تلقائي للملفات <b>الجديدة</b> التي تحمل توقيع Webshell مؤكد</label>
<label>مدة الحظر التلقائي (ساعات)</label><input type="text" name="block_hours" value="<?= $v('block_hours', 24) ?>" dir="ltr">
<label>IPs مستثناة من الحظر والإغلاق (IP مكتبك وبيتك — واحد بكل سطر)</label><textarea name="allow_ips" rows="3" dir="ltr"><?= h(setting('allow_ips', '')) ?></textarea>
<p class="meta">IP جهازك الحالي: <code><?= h($_SERVER['REMOTE_ADDR'] ?? '') ?></code></p>
<label>تنبيه هجوم: عدد الطلبات الهجومية من IP واحد / 5 دقائق</label><input type="text" name="atk_min" value="<?= $v('atk_min', 5) ?>" dir="ltr">
<label>تنبيه إغراق: إجمالي طلبات الموقع / 5 دقائق (و4 أضعاف المعدل)</label><input type="text" name="rq_min" value="<?= $v('rq_min', 500) ?>" dir="ltr">
<label>طلبات من IP واحد / 5 دقائق</label><input type="text" name="ip_max" value="<?= $v('ip_max', 300) ?>" dir="ltr">
<label>محاولات دخول (POST) من IP واحد / 5 دقائق</label><input type="text" name="login_max" value="<?= $v('login_max', 20) ?>" dir="ltr">
<label>مدة حفظ سجل الطلبات (أيام)</label><input type="text" name="keep_days" value="<?= $v('keep_days', 7) ?>" dir="ltr">
<p><button>حفظ</button></p></form></details></div>

<?php $sites = []; foreach (q('SELECT id, name FROM gm_sites') as $x) $sites[$x['id']] = $x['name'];
$bl = q('SELECT * FROM gm_blocks WHERE expires IS NULL OR expires>? ORDER BY id DESC LIMIT 300', [now()])->fetchAll(); ?>
<div class="card"><details <?= $bl ? 'open' : '' ?>><summary>⛔ الـ IPs المحظورة (<?= count($bl) ?>)</summary><div class="ov"><table>
<?php foreach ($bl as $b): ?><tr><td><?= ip_link($b['ip']) ?></td><td><?= $b['site_id'] ? h($sites[$b['site_id']] ?? '?') : 'كل المواقع' ?></td><td><?= h($b['reason']) ?> <small>(<?= h($b['actor']) ?>)</small></td>
<td>حتى <?= h($b['expires'] ?? 'دائم') ?></td><td><?= f('unblock', 'رفع', ['bid' => $b['id']]) ?></td></tr><?php endforeach ?></table></div>
<form method="post" class="acts"><?= csrf_in() ?><input type="hidden" name="scope" value="0"><input type="hidden" name="hours" value="0">
<input type="text" name="ip" placeholder="IP" dir="ltr" style="width:auto;flex:1"><input type="text" name="reason" placeholder="السبب" style="width:auto;flex:1"><button class="r" name="act" value="block">حظر دائم على كل المواقع</button></form>
<p class="meta">الحظر يُطبَّق على المواقع المربوط بها الحارس فقط.</p></details></div>

<?php $pk = ssh_pubkey(); ?><div class="card"><details><summary>🔌 مفتاح SSH للمراقب</summary>
<?php if ($pk): ?><p>أضف هذا المفتاح العام إلى <b>SSH Keys</b> في لوحة كل استضافة تريد ربطها:</p><textarea rows="3" dir="ltr" readonly onclick="this.select()"><?= h($pk) ?></textarea>
<p class="meta">المفتاح الخاص محفوظ في <code><?= h(ssh_key_path()) ?></code> — يجب أن يكون خارج مجلد الويب، ولا تشاركه. من يملكه يدخل كل استضافاتك.</p>
<?php else: ?><p>لا يوجد مفتاح بعد.</p><?= f('sshkey', 'إنشاء مفتاح', [], '') ?><?php endif ?></details></div>

<div class="card"><details><summary>🔐 تغيير كلمة المرور</summary><form method="post"><?= csrf_in() ?><input type="hidden" name="act" value="passwd">
<label>الحالية</label><input type="password" name="old" required><label>الجديدة (10 أحرف فأكثر)</label><input type="password" name="new" minlength="10" required>
<p><button>تغيير</button></p></form></details></div><?php
}
function view_log(): void {
    $sites = []; foreach (q('SELECT id, name FROM gm_sites') as $x) $sites[$x['id']] = $x['name']; ?>
<h2>سجل الإجراءات (يدوية وتلقائية) — آخر 300</h2><div class="card ov"><table class="tl"><tr><th>الوقت</th><th>الموقع</th><th>المنفّذ</th><th>الإجراء</th><th>التفاصيل</th></tr>
<?php foreach (q('SELECT * FROM gm_actions ORDER BY id DESC LIMIT 300') as $a): ?>
<tr><td><?= h($a['at']) ?></td><td><?= $a['site_id'] ? h($sites[$a['site_id']] ?? '?') : '—' ?></td><td><?= h($a['actor']) ?></td><td><?= h($a['action']) ?></td><td style="word-break:break-word"><?= h($a['detail']) ?></td></tr>
<?php endforeach ?></table></div><?php
}

/* ================= تقرير الحادث (للطباعة / PDF) ================= */
function view_report(array $s): void {
    $id = (int)$s['id']; $from = ago(30 * 86400);
    $au = json_decode($s['audit'] ?? '', true) ?: ['findings' => []];
    $issues = q('SELECT * FROM gm_issues WHERE site_id=? AND opened_at>? ORDER BY id', [$id, $from])->fetchAll();
    $files = q('SELECT * FROM gm_filelog WHERE site_id=? AND at>? ORDER BY id LIMIT 500', [$id, $from])->fetchAll();
    $qs = q('SELECT * FROM gm_quarantine WHERE site_id=? ORDER BY id', [$id])->fetchAll();
    $atk = q("SELECT ip, tag, COUNT(*) c, MIN(at) f, MAX(at) l FROM gm_requests WHERE site_id=? AND tag<>'' GROUP BY ip, tag ORDER BY c DESC LIMIT 40", [$id])->fetchAll();
    $acts = q('SELECT * FROM gm_actions WHERE site_id=? AND at>? ORDER BY id', [$id, $from])->fetchAll(); ?>
<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تقرير أمني — <?= h($s['name']) ?></title><style>
body{font:14px/1.7 system-ui,Tahoma,sans-serif;color:#111;max-width:900px;margin:auto;padding:20px}h1{font-size:22px;border-bottom:3px solid #19b8b0;padding-bottom:8px}
h2{font-size:16px;margin-top:26px;color:#0b6b66}table{width:100%;border-collapse:collapse;font-size:12.5px}td,th{border:1px solid #ccc;padding:5px 7px;text-align:right;vertical-align:top;word-break:break-word}
th{background:#eef7f6}code{direction:ltr;display:inline-block;font-size:11.5px}.m{white-space:pre-wrap}@media print{.np{display:none}}
</style></head><body>
<button class="np" onclick="print()" style="padding:8px 16px">🖨️ طباعة / حفظ PDF</button>
<h1>تقرير أمني — <?= h($s['name']) ?></h1>
<table><tr><th>الموقع</th><td><?= h($s['url']) ?></td><th>تاريخ التقرير</th><td><?= now() ?></td></tr>
<tr><th>درجة الأمان</th><td><?= $s['score'] === null ? '—' : (int)$s['score'] . '/100' ?></td><th>الفترة</th><td>آخر 30 يوم</td></tr>
<tr><th>الملفات المراقَبة</th><td><?= (int)$s['files_count'] ?></td><th>خوادم DNS</th><td><?= h($s['dns_base'] ?? '—') ?></td></tr></table>

<h2>1. الحوادث والتنبيهات</h2><?php if (!$issues): ?><p>لا توجد.</p><?php else: ?><table><tr><th>النوع</th><th>البداية</th><th>النهاية</th><th>التفاصيل</th></tr>
<?php foreach ($issues as $i): ?><tr><td><?= GM_TYPES[$i['type']][1] ?></td><td><?= h($i['opened_at']) ?></td><td><?= h($i['closed_at'] ?? 'مفتوح') ?></td><td class="m"><?= h($i['message']) ?></td></tr><?php endforeach ?></table><?php endif ?>

<h2>2. تغييرات الملفات</h2><?php if (!$files): ?><p>لا توجد.</p><?php else: ?><table><tr><th>الوقت</th><th>التغيير</th><th>الملف</th><th>مؤشرات</th></tr>
<?php foreach ($files as $x): ?><tr><td><?= h($x['at']) ?></td><td><?= ['added' => 'جديد', 'mod' => 'معدّل', 'removed' => 'محذوف'][$x['chg']] ?></td><td><code><?= h($x['path']) ?></code></td><td><?= h($x['sus'] ?? '') ?></td></tr><?php endforeach ?></table><?php endif ?>

<h2>3. الأدلة المحجوزة (الحجر)</h2><?php if (!$qs): ?><p>لا توجد.</p><?php else: ?><table><tr><th>الملف</th><th>SHA-256</th><th>تعديل الملف</th><th>وقت العزل</th><th>السبب</th><th>الحالة</th></tr>
<?php foreach ($qs as $x): ?><tr><td><code><?= h($x['path']) ?></code></td><td><code><?= h($x['sha256']) ?></code></td><td><?= h($x['mtime']) ?></td><td><?= h($x['at']) ?></td><td><?= h($x['reason']) ?> (<?= h($x['actor']) ?>)</td><td><?= ['held' => 'محجوز', 'restored' => 'أُرجع', 'deleted' => 'حُذف'][$x['state']] ?></td></tr><?php endforeach ?></table><?php endif ?>

<h2>4. مصادر الهجمات</h2><?php if (!$atk): ?><p>لا توجد.</p><?php else: ?><table><tr><th>IP</th><th>نوع الهجوم</th><th>العدد</th><th>أول مرة</th><th>آخر مرة</th></tr>
<?php foreach ($atk as $a): ?><tr><td><code><?= h($a['ip']) ?></code></td><td><?= h(GM_TAGS[$a['tag']] ?? $a['tag']) ?></td><td><?= (int)$a['c'] ?></td><td><?= h($a['f']) ?></td><td><?= h($a['l']) ?></td></tr><?php endforeach ?></table><?php endif ?>

<h2>5. الثغرات والإعدادات الخطرة</h2><?php if (!$au['findings']): ?><p>لا توجد ملاحظات.</p><?php else: ?><table><tr><th>الخطورة</th><th>الملاحظة</th><th>التفاصيل والحل</th></tr>
<?php foreach ($au['findings'] as $x): ?><tr><td><?= ['high' => 'خطير', 'med' => 'متوسط', 'low' => 'منخفض'][$x[0]] ?></td><td><?= h($x[1]) ?></td><td class="m"><?= h($x[2]) ?></td></tr><?php endforeach ?></table><?php endif ?>

<h2>6. إجراءات الاستجابة المتخذة</h2><?php if (!$acts): ?><p>لا توجد.</p><?php else: ?><table><tr><th>الوقت</th><th>المنفّذ</th><th>الإجراء</th><th>التفاصيل</th></tr>
<?php foreach ($acts as $a): ?><tr><td><?= h($a['at']) ?></td><td><?= h($a['actor']) ?></td><td><?= h($a['action']) ?></td><td><?= h($a['detail']) ?></td></tr><?php endforeach ?></table><?php endif ?>
<p style="margin-top:30px;color:#666;font-size:12px">أُنشئ آلياً بواسطة GHANI Monitor. الأوقات بتوقيت بغداد.</p></body></html><?php
}
