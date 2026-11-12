<?php
/* ================= مفردات الواجهة ================= */
const GM_SEV = [   // نوع التنبيه => درجة الخطورة
    'malware' => 'crit', 'deface' => 'crit', 'redirect' => 'crit', 'dns' => 'crit', 'files' => 'crit',
    'scripts' => 'high', 'agent' => 'high', 'attack' => 'high', 'brute' => 'high', 'flood' => 'high', 'down' => 'high',
    'vuln' => 'med', 'ipflood' => 'med', 'title' => 'med', 'keyword' => 'med', 'ssl' => 'low',
];
const SEV_NAME = ['crit' => 'حرج', 'high' => 'عالٍ', 'med' => 'متوسط', 'low' => 'منخفض'];
const LV_NAME = ['ok' => 'سليم', 'warn' => 'تحذير', 'danger' => 'خطر', 'down' => 'متوقف', 'wait' => 'بانتظار الفحص', 'lock' => 'مغلق'];
const CHG_NAME = ['added' => 'جديد', 'mod' => 'معدّل', 'removed' => 'محذوف'];

function csrf_in(): string {
    global $csrf;
    return '<input type="hidden" name="csrf" value="' . $csrf . '"><input type="hidden" name="ret" value="' . h('?' . ($_SERVER['QUERY_STRING'] ?? '')) . '">';
}
function f(string $act, string $label, array $fields = [], string $cls = '', string $confirm = ''): string {
    $o = '<form class="i" method="post"' . ($confirm ? ' onsubmit="return confirm(\'' . h($confirm) . '\')"' : '') . '>' . csrf_in();
    foreach ($fields as $k => $v) $o .= '<input type="hidden" name="' . h($k) . '" value="' . h($v) . '">';
    return $o . '<button class="btn ' . $cls . '" name="act" value="' . h($act) . '">' . $label . '</button></form>';
}
// نصوص التنبيهات مكتوبة لتيليگرام وفيها رموز؛ في اللوحة تُعرض نصاً صافياً
function plain(string $m): string { return trim(preg_replace(['~[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{FE0F}]\s?~u', '~\n{3,}~'], ['', "\n\n"], $m)); }
function sev_chip(string $k): string { return '<span class="sv sv-' . $k . '"><i></i>' . SEV_NAME[$k] . '</span>'; }
function find_chip(string $s): string { return sev_chip(['high' => 'crit', 'med' => 'med', 'low' => 'low'][$s]); }
function lv_chip(string $lv): string { return '<span class="st st-' . $lv . '"><i></i>' . LV_NAME[$lv] . '</span>'; }
function score_bar($sc): string {
    if ($sc === null) return '<span class="mut">لم يُدقَّق</span>';
    $c = $sc >= 80 ? 'ok' : ($sc >= 50 ? 'med' : 'crit');
    return '<span class="score" title="درجة الأمان"><span class="score-t"><span class="score-f c-' . $c . '" style="width:' . (int)$sc . '%"></span></span><b>' . (int)$sc . '</b></span>';
}
function ip_link(string $ip): string { return '<a class="mono" href="?ip=' . urlencode($ip) . '">' . h($ip) . '</a>'; }
function site_level(array $s, array $open): string {
    if ($s['lockdown']) return 'lock';
    $lv = $s['last_check'] ? 'ok' : 'wait';
    foreach ($open as $i) {
        $l = GM_TYPES[$i['type']][2];
        if ($l === 'danger' || ($l === 'down' && $lv !== 'danger') || ($l === 'warn' && ($lv === 'ok' || $lv === 'wait'))) $lv = $l;
    }
    return $lv;
}
function conn_label(array $s): string {
    if (!has_agent($s)) return '<span class="mut">بدون وكيل</span>';
    $how = $s['ssh_host'] ? 'SSH' : 'وكيل';
    if ($s['agent_ok'] === null) return '<span class="mut">' . $how . ' — بانتظار الربط</span>';
    return $s['agent_ok'] ? '<span class="ok-t">' . $how . ' متصل</span>' : '<span class="bad-t">' . $how . ' مقطوع</span>';
}
function icon(string $n): string {
    static $p = [
        'home' => '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
        'alert' => '<path d="M12 3 2.5 20h19L12 3z"/><path d="M12 10v4.5M12 17.5v.5"/>',
        'asset' => '<rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/><path d="M7 7h.01M7 17h.01"/>',
        'target' => '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3"/><path d="M12 1.5v4M12 18.5v4M1.5 12h4M18.5 12h4"/>',
        'box' => '<path d="M3.5 7.5 12 3l8.5 4.5v9L12 21l-8.5-4.5v-9z"/><path d="M3.5 7.5 12 12l8.5-4.5M12 12v9"/>',
        'log' => '<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
        'gear' => '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"/>',
    ];
    return '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' . $p[$n] . '</svg>';
}

/* ================= الهيكل ================= */
function page_top(string $title, bool $nav = true, string $cur = '', int $refresh = 0): void {
    // التواريخ والأوقات تُعرض من اليسار لليمين حتى لا تنقلب داخل النص العربي
    ob_start(fn($o) => preg_replace('~(?<![\w"=/-])(\d{4}-\d\d-\d\d(?: \d\d:\d\d(?::\d\d)?)?)(?![\w"-])~', '<bdi dir="ltr">$1</bdi>', $o));
    $flash = $_SESSION['flash'] ?? ''; unset($_SESSION['flash']); $GLOBALS['gm_nav'] = $nav; ?>
<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><meta name="referrer" content="no-referrer"><?= $refresh ? '<meta http-equiv="refresh" content="' . $refresh . '">' : '' ?>
<title><?= h($title) ?></title><style>
@font-face{font-family:"Plex AR";src:url(assets/plex-arabic-400.woff2) format("woff2");font-weight:400;font-display:swap;unicode-range:U+0600-06FF,U+0750-077F,U+FB50-FDFF,U+FE70-FEFF}
@font-face{font-family:"Plex AR";src:url(assets/plex-arabic-600.woff2) format("woff2");font-weight:600;font-display:swap;unicode-range:U+0600-06FF,U+0750-077F,U+FB50-FDFF,U+FE70-FEFF}
@font-face{font-family:"Plex AR";src:url(assets/plex-latin-400.woff2) format("woff2");font-weight:400;font-display:swap;unicode-range:U+0000-00FF,U+2000-206F}
@font-face{font-family:"Plex AR";src:url(assets/plex-latin-600.woff2) format("woff2");font-weight:600;font-display:swap;unicode-range:U+0000-00FF,U+2000-206F}
:root{--s0:#0e1524;--s1:#151e31;--s2:#1c2740;--ln:#26334f;--tx:#e3e9f4;--mu:#8c9ab8;--brand:#1fb5ac;--series:#4c8df6;
  --crit:#d03b3b;--high:#ec835a;--med:#fab219;--low:#8a98b5;--ok:#0ca30c;--ok-t:#3fc66a;--bad-t:#ff8a80}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--s0);color:var(--tx);font:14px/1.6 "Plex AR","Segoe UI",Tahoma,sans-serif}
a{color:#7fb2ff;text-decoration:none}a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
.mono,code{font-family:ui-monospace,"Cascadia Mono",Consolas,monospace;font-size:12.5px;direction:ltr;unicode-bidi:isolate;word-break:break-all}
code{background:var(--s0);border:1px solid var(--ln);border-radius:3px;padding:0 5px;display:inline-block}
.mut{color:var(--mu)}.ok-t{color:var(--ok-t)}.bad-t{color:var(--bad-t)}.num{font-variant-numeric:tabular-nums}
/* الهيكل: شريط جانبي ثابت + محتوى */
.shell{display:grid;grid-template-columns:212px 1fr;min-height:100vh}
.rail{background:var(--s1);border-inline-end:1px solid var(--ln);padding:14px 0;position:sticky;top:0;height:100vh;display:flex;flex-direction:column}
.brand{display:flex;align-items:center;gap:9px;padding:2px 16px 16px;font-weight:600;font-size:15px;color:var(--tx)}
.brand svg{width:26px;height:26px;flex:none}
.rail a.nv{display:flex;align-items:center;gap:10px;padding:8px 16px;color:var(--mu);border-inline-start:3px solid transparent}
.rail a.nv:hover{background:var(--s2);color:var(--tx);text-decoration:none}
.rail a.nv.on{color:var(--tx);background:var(--s2);border-inline-start-color:var(--brand)}
.rail a.nv b{margin-inline-start:auto;background:var(--crit);color:#fff;border-radius:9px;padding:0 7px;font-size:12px;font-weight:600}
.ic{width:17px;height:17px;flex:none}.rail .foot{margin-top:auto;padding:10px 16px 0;border-top:1px solid var(--ln)}
.main{min-width:0;padding:0 18px 40px}
.top{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:12px 0;border-bottom:1px solid var(--ln);margin-bottom:14px}
.top h1{font-size:17px;font-weight:600;margin:0;margin-inline-end:auto}
.beat{display:flex;align-items:center;gap:7px;color:var(--mu);font-size:12.5px}
.beat i{width:8px;height:8px;border-radius:50%;background:var(--ok)}.beat.stale i{background:var(--crit)}
/* اللوحات */
.pn{background:var(--s1);border:1px solid var(--ln);border-radius:5px;margin-bottom:14px;min-width:0;overflow:hidden}
.pn>h2{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0;padding:9px 13px;font-size:13.5px;font-weight:600;border-bottom:1px solid var(--ln)}
.pn>h2 small{font-weight:400;color:var(--mu);font-size:12.5px}.pn>h2 .sp{margin-inline-start:auto}
.pb{padding:12px 13px}.pb>p:first-child{margin-top:0}.pb>p:last-child{margin-bottom:0}
.g2{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:14px}.g2>.pn{margin-bottom:0}.g2{margin-bottom:14px}
/* شريط الوضع العام + المؤشرات */
.posture{display:flex;align-items:center;gap:14px;flex-wrap:wrap;border:1px solid var(--ln);border-inline-start:5px solid var(--ok);background:var(--s1);border-radius:5px;padding:11px 14px;margin-bottom:14px}
.posture.p-crit{border-inline-start-color:var(--crit)}.posture.p-high{border-inline-start-color:var(--high)}.posture.p-med{border-inline-start-color:var(--med)}.posture.p-low{border-inline-start-color:var(--low)}
.posture b{font-size:16px;font-weight:600}.posture span{color:var(--mu)}
.kpi{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:1px;background:var(--ln);border:1px solid var(--ln);border-radius:5px;overflow:hidden;margin-bottom:14px}
.kpi a,.kpi div{background:var(--s1);padding:10px 12px;color:var(--tx);display:block;border-top:3px solid transparent}
.kpi a:hover{background:var(--s2);text-decoration:none}
.kpi b{display:block;font-size:24px;font-weight:600;line-height:1.2;font-variant-numeric:tabular-nums}.kpi span{color:var(--mu);font-size:12.5px}
.kpi .k-crit{border-top-color:var(--crit)}.kpi .k-high{border-top-color:var(--high)}.kpi .k-med{border-top-color:var(--med)}.kpi .k-low{border-top-color:var(--low)}
/* الجداول */
.ov{overflow-x:auto}table.gr{width:100%;border-collapse:collapse;font-size:13px}
.gr th{color:var(--mu);font-weight:400;font-size:12.5px;text-align:start;padding:7px 10px;border-bottom:1px solid var(--ln);white-space:nowrap}
.gr td{padding:7px 10px;border-bottom:1px solid var(--ln);vertical-align:top}.gr tr:last-child td{border-bottom:0}
.gr tbody tr:hover td{background:var(--s2)}.gr td.nw{white-space:nowrap}.gr td.end,.gr th.end{text-align:end}
.gr td.sev{border-inline-start:3px solid var(--low);white-space:nowrap}.gr tr.r-crit td.sev{border-inline-start-color:var(--crit)}.gr tr.r-high td.sev{border-inline-start-color:var(--high)}.gr tr.r-med td.sev{border-inline-start-color:var(--med)}
.gr td.w{min-width:170px}.msg{white-space:pre-wrap;word-break:break-word;color:var(--mu);font-size:12.5px;margin-top:3px}
/* الشارات */
.sv,.st{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;white-space:nowrap}
.sv i,.st i{width:9px;height:9px;border-radius:2px;background:var(--low);flex:none}.st i{border-radius:50%}
.sv-crit i{background:var(--crit)}.sv-high i{background:var(--high)}.sv-med i{background:var(--med)}.sv-crit{font-weight:600}
.st-ok i{background:var(--ok)}.st-warn i{background:var(--med)}.st-danger i{background:var(--crit)}.st-down i{background:var(--high)}.st-lock i{background:#a78bfa}
.tag{border:1px solid var(--ln);border-radius:3px;padding:0 6px;font-size:12px;white-space:nowrap}
.score{display:inline-flex;align-items:center;gap:8px}.score-t{width:64px;height:6px;background:var(--s0);border-radius:3px;overflow:hidden;display:block}
.score-f{display:block;height:100%}.c-ok{background:var(--ok)}.c-med{background:var(--med)}.c-crit{background:var(--crit)}.score b{font-weight:600;font-variant-numeric:tabular-nums}
/* النماذج والأزرار */
input,select,textarea{font:inherit;color:var(--tx);background:var(--s0);border:1px solid var(--ln);border-radius:4px;padding:6px 9px;max-width:100%}
input[type=text],input[type=url],input[type=password],textarea,select.w{width:100%}
label{display:block;margin:10px 0 3px;color:var(--mu);font-size:12.5px}label.ck{color:var(--tx);font-size:13.5px}
.btn{font:inherit;font-size:13px;cursor:pointer;background:var(--s2);border:1px solid var(--ln);color:var(--tx);border-radius:4px;padding:5px 11px;display:inline-block;white-space:nowrap}
.btn:hover{border-color:var(--mu);text-decoration:none}.btn.pri{background:var(--brand);border-color:var(--brand);color:#04211f;font-weight:600}
.btn.dng{border-color:#7a2b2b;color:var(--bad-t)}.btn.dng:hover{background:#3a1717}.btn.sm{padding:2px 8px;font-size:12.5px}
form.i{display:inline}.acts{display:flex;gap:7px;flex-wrap:wrap;align-items:center}
.flash{background:#10302e;border:1px solid var(--brand);border-radius:4px;padding:9px 12px;margin-bottom:14px}
.note{border:1px solid var(--ln);border-inline-start:3px solid var(--med);background:var(--s0);border-radius:4px;padding:8px 11px;margin-bottom:14px}
/* تبويبات الأصل */
.tabs{display:flex;gap:2px;border-bottom:1px solid var(--ln);margin-bottom:14px;overflow-x:auto}
.tabs a{padding:8px 14px;color:var(--mu);white-space:nowrap;border-bottom:2px solid transparent}.tabs a:hover{color:var(--tx);text-decoration:none}
.tabs a.on{color:var(--tx);border-bottom-color:var(--brand)}.tabs a b{color:var(--bad-t);font-weight:600}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));border-top:1px solid var(--ln);overflow:hidden}
.facts div{padding:9px 13px;border-inline-end:1px solid var(--ln);border-bottom:1px solid var(--ln);margin-bottom:-1px}.facts span{display:block;color:var(--mu);font-size:12.5px}.facts b{font-weight:600;word-break:break-word}
/* الرسوم */
.chart{direction:ltr;display:block;width:100%;height:auto}.chart text{fill:var(--mu);font-size:11px;font-family:inherit}
.chart .gl{stroke:var(--ln);stroke-width:1}.chart .bar{fill:var(--series)}.chart .hit{fill:transparent}.chart .hit:hover+.bar,.chart g:hover .bar{fill:#8ab6ff}
.hb{display:grid;grid-template-columns:auto 1fr auto;gap:5px 10px;align-items:center}.hb span.t{display:block;height:8px;background:var(--s0);border-radius:4px 0 0 4px;overflow:hidden}
.hb span.t i{display:block;height:100%;background:var(--series);border-radius:4px 0 0 4px}
#tip{position:fixed;pointer-events:none;background:#05080f;border:1px solid var(--ln);border-radius:4px;padding:4px 9px;font-size:12.5px;display:none;z-index:9;white-space:nowrap}
pre.src{direction:ltr;text-align:left;background:#0a0f1b;border:1px solid var(--ln);border-radius:5px;padding:8px 0;overflow:auto;font:12px/1.55 ui-monospace,Consolas,monospace;max-height:72vh;margin:0}
pre.src span{display:block;white-space:pre;padding:0 10px}pre.src span.hot{background:#48191b;box-shadow:inset 3px 0 0 var(--crit)}pre.src i{color:#55627f;font-style:normal;user-select:none;display:inline-block;width:40px}
.empty{color:var(--mu);padding:18px 13px;text-align:center}
@media (max-width:900px){
  .shell{display:block}.rail{position:static;height:auto;flex-direction:row;align-items:center;padding:0;overflow-x:auto;border-inline-end:0;border-bottom:1px solid var(--ln)}
  .brand{padding:10px 12px}.brand span{display:none}.rail a.nv{padding:11px 11px;border-inline-start:0;border-bottom:3px solid transparent;white-space:nowrap}
  .rail a.nv.on{border-bottom-color:var(--brand)}.rail .foot{margin:0;padding:0 10px;border:0}
  .main{padding:0 11px 30px}.g2{grid-template-columns:minmax(0,1fr)}.kpi{grid-template-columns:repeat(4,minmax(0,1fr))}.kpi b{font-size:20px}.hm{display:none}
}
@media (max-width:480px){.kpi{grid-template-columns:repeat(2,minmax(0,1fr))}.chart text{font-size:19px}}
@media (prefers-reduced-motion:no-preference){.beat:not(.stale) i{animation:bt 2.4s ease-in-out infinite}@keyframes bt{50%{opacity:.35}}}
</style></head><body>
<?php if (!$nav) { echo '<div class="main" style="max-width:440px;margin:8vh auto 0">'; if ($flash) echo '<div class="flash">' . h($flash) . '</div>'; return; }
    $nOpen = (int)q('SELECT COUNT(*) FROM gm_issues WHERE closed_at IS NULL')->fetchColumn();
    $last = setting('last_cron'); $stale = !$last || strtotime($last) < time() - 900;
    $items = ['' => ['home', 'نظرة عامة'], 'alerts' => ['alert', 'التنبيهات'], 'assets' => ['asset', 'الأصول'], 'attackers' => ['target', 'المهاجمون'],
              'quarantine' => ['box', 'الحجر'], 'log' => ['log', 'سجل الإجراءات'], 'settings' => ['gear', 'الإعدادات']]; ?>
<div class="shell"><aside class="rail">
  <a class="brand" href="?"><svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="6" fill="#1fb5ac"/><circle cx="13" cy="16" r="6" fill="none" stroke="#fff" stroke-width="2.2"/><circle cx="19" cy="16" r="6" fill="none" stroke="#fff" stroke-width="2.2"/></svg><span>GHANI SOC</span></a>
  <?php foreach ($items as $k => [$ic, $lb]): ?><a class="nv<?= $cur === $k ? ' on' : '' ?>" href="?<?= $k ? 'v=' . $k : '' ?>"><?= icon($ic) ?><span><?= $lb ?></span><?= $k === 'alerts' && $nOpen ? "<b>$nOpen</b>" : '' ?></a><?php endforeach ?>
  <div class="foot"><?= f('logout', 'خروج', [], 'sm') ?></div>
</aside><div class="main">
<div class="top"><h1><?= h($title) ?></h1>
  <span class="beat<?= $stale ? ' stale' : '' ?>"><i></i><?= $stale ? 'الفحص الدوري متوقف' : 'آخر فحص ' . h(substr((string)$last, 11, 5)) ?></span><?= f('run', 'افحص الآن') ?></div>
<?php if ($flash): ?><div class="flash"><?= h($flash) ?></div><?php endif;
    if ($stale): ?><div class="note">الفحص الدوري لم يعمل منذ <?= h($last ?: 'التنصيب') ?>. تأكد من تشغيل cron كل 5 دقائق.</div><?php endif;
}
function page_end(): void { ?>
</div><?= !empty($GLOBALS['gm_nav']) ? '</div>' : '' ?><div id="tip"></div><script>
(function(){var t=document.getElementById('tip');if(!t)return;
document.addEventListener('mousemove',function(e){var el=e.target.closest&&e.target.closest('[data-tip]');
if(!el){t.style.display='none';return}t.textContent=el.getAttribute('data-tip');t.style.display='block';
var x=e.clientX+14,y=e.clientY+14;if(x+t.offsetWidth>innerWidth-8)x=e.clientX-t.offsetWidth-14;t.style.left=x+'px';t.style.top=y+'px'});})();
</script></body></html><?php ob_end_flush();
}

/* ================= رسوم ================= */
function chart_hours(array $byHour, string $unit): string {
    $n = 24; $W = 720; $H = 190; $l = 34; $r = 8; $tp = 16; $b = 24; $pw = $W - $l - $r; $ph = $H - $tp - $b;
    $vals = []; $t0 = strtotime(date('Y-m-d H:00:00')) - 23 * 3600;
    for ($i = 0; $i < $n; $i++) { $k = date('Y-m-d H', $t0 + $i * 3600); $vals[] = [$k, (int)($byHour[$k] ?? 0)]; }
    $max = max(array_column($vals, 1));
    if (!$max) return '<div class="empty">لا توجد ' . $unit . ' خلال آخر 24 ساعة</div>';
    $mag = 10 ** floor(log10($max)); $top = (int)(ceil($max / $mag) * $mag); if ($top < 4) $top = 4;
    $o = '<svg class="chart" viewBox="0 0 ' . "$W $H" . '" role="img" aria-label="' . $unit . ' لكل ساعة خلال آخر 24 ساعة">';
    foreach ([0, .5, 1] as $g) { $y = $tp + $ph - $ph * $g; $o .= '<line class="gl" x1="' . $l . '" x2="' . ($W - $r) . '" y1="' . $y . '" y2="' . $y . '"/><text x="' . ($l - 6) . '" y="' . ($y + 4) . '" text-anchor="end">' . (int)($top * $g) . '</text>'; }
    $bw = $pw / $n; $peak = array_search($max, array_column($vals, 1));
    foreach ($vals as $i => [$k, $v]) {
        $x = $l + $i * $bw + 1; $w = $bw - 2; $hh = substr($k, 11, 2) . ':00';
        $bh = $v ? max(2, $ph * $v / $top) : 0; $y = $tp + $ph - $bh; $rr = min(4, $bh, $w / 2);
        $o .= '<g data-tip="' . $hh . ' — ' . $v . ' ' . $unit . '"><rect class="hit" x="' . ($x - 1) . '" y="' . $tp . '" width="' . $bw . '" height="' . $ph . '"/>';
        if ($v) $o .= '<path class="bar" d="M' . round($x, 1) . ' ' . ($tp + $ph) . 'V' . round($y + $rr, 1) . 'q0 -' . $rr . ' ' . $rr . ' -' . $rr . 'h' . round($w - 2 * $rr, 1) . 'q' . $rr . ' 0 ' . $rr . ' ' . $rr . 'V' . ($tp + $ph) . 'z"/>';
        $o .= '</g>';
        if ($i === $peak) $o .= '<text x="' . round($x + $w / 2, 1) . '" y="' . round($y - 4, 1) . '" text-anchor="middle" style="fill:var(--tx)">' . $v . '</text>';
        if ($i % 6 === 0 || $i === $n - 1) $o .= '<text x="' . round($x + $w / 2, 1) . '" y="' . ($H - 7) . '" text-anchor="middle">' . ($i === $n - 1 ? 'الآن' : $hh) . '</text>';
    }
    return $o . '</svg>';
}
function hbars(array $rows): string {          // [label => count]
    if (!$rows) return '<div class="empty">لا توجد بيانات</div>';
    $max = max($rows); $o = '<div class="hb">';
    foreach ($rows as $k => $c) $o .= '<span>' . h($k) . '</span><span class="t" data-tip="' . h($k) . ' — ' . (int)$c . '"><i style="width:' . max(2, round(100 * $c / $max)) . '%"></i></span><b class="num">' . (int)$c . '</b>';
    return $o . '</div>';
}
function alerts_table(array $rows, bool $withSite = true, bool $withMsg = false): string {
    if (!$rows) return '<div class="empty">لا توجد تنبيهات</div>';
    $o = '<div class="ov"><table class="gr"><thead><tr><th>الخطورة</th><th>التنبيه</th>' . ($withSite ? '<th>الأصل</th>' : '') . '<th>بدأ</th><th class="hm">الحالة</th></tr></thead><tbody>';
    foreach ($rows as $i) {
        $sv = GM_SEV[$i['type']] ?? 'low';
        $o .= '<tr class="r-' . $sv . '"><td class="sev">' . sev_chip($sv) . '</td><td class="w"><a href="?site=' . (int)$i['site_id'] . '">' . GM_TYPES[$i['type']][1] . '</a>' . ($withMsg ? '<div class="msg">' . h(plain($i['message'])) . '</div>' : '') . '</td>'
            . ($withSite ? '<td>' . h($i['name'] ?? '') . '</td>' : '') . '<td class="nw num">' . h($i['opened_at']) . '</td><td class="hm nw">' . ($i['closed_at'] ? '<span class="mut">أُغلق ' . h($i['closed_at']) . '</span>' : 'مفتوح') . '</td></tr>';
    }
    return $o . '</tbody></table></div>';
}
function assets_table(array $sites, array $open): string {
    if (!$sites) return '<div class="empty">لا توجد أصول بعد. أضف أول موقع من صفحة «الأصول».</div>';
    $o = '<div class="ov"><table class="gr"><thead><tr><th>الأصل</th><th>الحالة</th><th>درجة الأمان</th><th class="hm end">الاستجابة</th><th class="hm end">طلبات / 5 د</th><th class="hm">الاتصال</th><th class="end">تنبيهات</th></tr></thead><tbody>';
    foreach ($sites as $s) {
        $tr = !empty($s['traffic_last']) ? json_decode($s['traffic_last'], true) : null; $n = count($open[$s['id']] ?? []);
        $o .= '<tr><td><a href="?site=' . $s['id'] . '"><b>' . h($s['name']) . '</b></a><div class="mut"><span class="mono">' . h(host_of($s['url'])) . '</span></div></td><td>' . lv_chip(site_level($s, $open[$s['id']] ?? [])) . '</td><td>' . score_bar($s['score']) . '</td>'
            . '<td class="hm end num">' . ($s['resp_ms'] === null ? '—' : '<bdi dir="ltr">' . (int)$s['resp_ms'] . ' ms</bdi>') . '</td><td class="hm end num">' . ($tr ? (int)$tr['total'] : '—') . '</td><td class="hm">' . conn_label($s) . '</td><td class="end num">' . ($n ?: '<span class="mut">0</span>') . '</td></tr>';
    }
    return $o . '</tbody></table></div>';
}
function load_sites(): array {
    $sites = q('SELECT * FROM gm_sites ORDER BY id')->fetchAll(); $open = [];
    foreach (q('SELECT i.*, s.name FROM gm_issues i JOIN gm_sites s ON s.id=i.site_id WHERE i.closed_at IS NULL ORDER BY i.id DESC')->fetchAll() as $i) $open[$i['site_id']][] = $i;
    return [$sites, $open];
}

/* ================= نظرة عامة ================= */
function view_overview(): void {
    [$sites, $open] = load_sites();
    $all = $open ? array_merge(...array_values($open)) : [];
    $by = ['crit' => 0, 'high' => 0, 'med' => 0, 'low' => 0];
    foreach ($all as $i) $by[GM_SEV[$i['type']] ?? 'low']++;
    usort($all, fn($a, $b) => array_search(GM_SEV[$a['type']] ?? 'low', array_keys(SEV_NAME)) <=> array_search(GM_SEV[$b['type']] ?? 'low', array_keys(SEV_NAME)) ?: strcmp($b['opened_at'], $a['opened_at']));
    $worst = $by['crit'] ? 'crit' : ($by['high'] ? 'high' : ($by['med'] ? 'med' : ($by['low'] ? 'low' : 'ok')));
    $healthy = count(array_filter($sites, fn($s) => site_level($s, $open[$s['id']] ?? []) === 'ok'));
    $atk = (int)q("SELECT COUNT(*) FROM gm_requests WHERE tag<>'' AND at>?", [ago(86400)])->fetchColumn();
    $blk = (int)q('SELECT COUNT(*) FROM gm_blocks WHERE expires IS NULL OR expires>?', [now()])->fetchColumn();
    $qn = (int)q("SELECT COUNT(*) FROM gm_quarantine WHERE state='held'")->fetchColumn();
    $hours = []; foreach (q("SELECT SUBSTR(at,1,13) h, COUNT(*) c FROM gm_requests WHERE tag<>'' AND at>? GROUP BY h", [ago(86400)]) as $r) $hours[$r['h']] = $r['c'];
    $types = []; foreach (q("SELECT tag, COUNT(*) c FROM gm_requests WHERE tag<>'' AND at>? GROUP BY tag ORDER BY c DESC", [ago(86400)]) as $r) $types[GM_TAGS[$r['tag']] ?? $r['tag']] = $r['c'];
    $say = ['crit' => 'وضع حرج: يوجد اختراق محتمل يحتاج تدخلك الآن', 'high' => 'تهديد نشط: هجمات أو أعطال قيد الحدوث', 'med' => 'يحتاج مراجعة: ثغرات أو تغييرات غير معتمدة', 'low' => 'ملاحظات بسيطة', 'ok' => 'الوضع مستقر: لا توجد تنبيهات مفتوحة']; ?>
<div class="posture p-<?= $worst ?>"><b><?= $say[$worst] ?></b><span><?= count($all) ?> تنبيه مفتوح على <?= count($open) ?> من <?= count($sites) ?> أصل</span></div>
<div class="kpi">
  <a class="k-crit" href="?v=alerts"><b><?= $by['crit'] ?></b><span>حرج</span></a><a class="k-high" href="?v=alerts"><b><?= $by['high'] ?></b><span>عالٍ</span></a>
  <a class="k-med" href="?v=alerts"><b><?= $by['med'] ?></b><span>متوسط</span></a><a class="k-low" href="?v=alerts"><b><?= $by['low'] ?></b><span>منخفض</span></a>
  <a href="?v=assets"><b><?= $healthy ?><small class="mut" style="font-size:14px"> / <?= count($sites) ?></small></b><span>أصول سليمة</span></a>
  <a href="?v=attackers"><b><?= $atk ?></b><span>طلب هجومي، 24 ساعة</span></a><a href="?v=settings"><b><?= $blk ?></b><span>IP محظور</span></a><a href="?v=quarantine"><b><?= $qn ?></b><span>ملف بالحجر</span></a>
</div>
<div class="g2">
  <section class="pn"><h2>الطلبات الهجومية لكل ساعة <small>آخر 24 ساعة، كل الأصول</small></h2><div class="pb"><?= chart_hours($hours, 'طلب هجومي') ?></div></section>
  <section class="pn"><h2>أنواع الهجمات <small>24 ساعة</small></h2><div class="pb"><?= hbars($types) ?></div></section>
</div>
<div class="g2">
  <section class="pn"><h2>طابور التنبيهات <small>المفتوحة، الأخطر أولاً</small><a class="sp" href="?v=alerts">الكل</a></h2><?= alerts_table(array_slice($all, 0, 10)) ?></section>
  <section class="pn"><h2>أكثر المهاجمين <small>24 ساعة</small><a class="sp" href="?v=attackers">الكل</a></h2>
  <?php $top = q("SELECT ip, COUNT(*) c, MAX(at) l FROM gm_requests WHERE tag<>'' AND at>? GROUP BY ip ORDER BY c DESC LIMIT 8", [ago(86400)])->fetchAll();
  if (!$top): ?><div class="empty">لا يوجد مهاجمون مسجّلون</div><?php else: ?><table class="gr"><thead><tr><th>IP</th><th class="end">طلبات</th><th class="end">آخر نشاط</th></tr></thead><tbody>
  <?php foreach ($top as $t): ?><tr><td><?= ip_link($t['ip']) ?></td><td class="end num"><?= (int)$t['c'] ?></td><td class="end nw num mut"><?= h(substr($t['l'], 11, 5)) ?></td></tr><?php endforeach ?></tbody></table><?php endif ?></section>
</div>
<section class="pn"><h2>الأصول <small><?= count($sites) ?> موقع</small><a class="sp" href="?v=assets">إدارة</a></h2><?= assets_table($sites, $open) ?></section><?php
}

/* ================= التنبيهات / الأصول / المهاجمون / الحجر ================= */
function view_alerts(): void {
    $st = ($_GET['st'] ?? 'open') === 'all' ? 'all' : 'open';
    $rows = q('SELECT i.*, s.name FROM gm_issues i LEFT JOIN gm_sites s ON s.id=i.site_id' . ($st === 'open' ? ' WHERE i.closed_at IS NULL' : '') . ' ORDER BY i.id DESC LIMIT 300')->fetchAll(); ?>
<div class="tabs"><a class="<?= $st === 'open' ? 'on' : '' ?>" href="?v=alerts">المفتوحة</a><a class="<?= $st === 'all' ? 'on' : '' ?>" href="?v=alerts&st=all">كل السجل</a></div>
<section class="pn"><h2><?= $st === 'open' ? 'تنبيهات مفتوحة' : 'آخر 300 تنبيه' ?> <small><?= count($rows) ?></small></h2><?= alerts_table($rows, true, true) ?></section><?php
}
function view_assets(): void {
    [$sites, $open] = load_sites(); ?>
<section class="pn"><h2>الأصول المراقَبة <small><?= count($sites) ?></small></h2><?= assets_table($sites, $open) ?></section>
<section class="pn"><h2>إضافة أصل</h2><div class="pb"><form method="post" style="max-width:640px"><?= csrf_in() ?><input type="hidden" name="act" value="add">
<label>الاسم</label><input type="text" name="name" placeholder="مثال: موقع الشركة">
<label>الرابط</label><input type="url" name="url" placeholder="https://example.com" required dir="ltr">
<label>كلمة ثابتة يجب أن تظهر بالصفحة (اختياري)</label><input type="text" name="keyword">
<label class="ck"><input type="checkbox" name="agent" checked> ملف الوكيل gm-agent.php: لازم لعدّ الطلبات وكشف الهجمات والحظر والإغلاق</label>
<label class="ck"><input type="checkbox" name="laravel"> الموقع Laravel (المجلد العام هو public)</label>
<label class="ck"><input type="checkbox" name="cf"> الموقع خلف Cloudflare</label>
<label class="ck"><input type="checkbox" name="deface" checked> فحص عبارات التشويه داخل المحتوى (ألغِه لمواقع تكتب عن الاختراق)</label>
<details style="margin-top:12px"><summary>اتصال SSH: فحص الملفات والعزل بدون رفع أي ملف (اختياري)</summary>
<label>الخادم (IP أو اسم)</label><input type="text" name="ssh_host" dir="ltr" placeholder="123.45.67.89">
<label>المنفذ (هوستنجر المشترك عادةً 65002)</label><input type="text" name="ssh_port" dir="ltr" value="65002">
<label>اسم المستخدم</label><input type="text" name="ssh_user" dir="ltr" placeholder="u123456789">
<label>المسار الكامل للمجلد العام</label><input type="text" name="ssh_path" dir="ltr" placeholder="/home/u123456789/domains/example.com/public_html">
<p class="mut">أضف المفتاح العام للمراقب (من الإعدادات) إلى SSH Keys في لوحة الاستضافة أولاً.</p></details>
<p><button class="btn pri">إضافة الأصل</button></p></form></div></section>
<section class="pn"><h2>استيراد جماعي <small>الصق قائمة JSON بكل مواقعك، مثلاً من مساعد هوستنجر</small></h2><div class="pb"><form method="post"><?= csrf_in() ?><input type="hidden" name="act" value="import">
<textarea name="json" rows="7" dir="ltr" required placeholder='[{"name":"My site","url":"https://example.com","ssh_host":"1.2.3.4","ssh_port":65002,"ssh_user":"u123456789","path":"/home/u123456789/domains/example.com/public_html","laravel":false,"cloudflare":false}]'></textarea>
<p class="mut">المواقع الموجودة مسبقاً تُتخطّى. حقول SSH اختيارية. لا تلصق كلمات سر: النظام لا يحتاجها.</p>
<p><button class="btn pri">استيراد</button></p></form></div></section><?php
}
function view_attackers(): void {
    $days = (int)($_GET['d'] ?? 1) === 7 ? 7 : 1;
    $sites = []; foreach (q('SELECT id, name FROM gm_sites') as $x) $sites[$x['id']] = $x['name'];
    $blocked = array_flip(q('SELECT ip FROM gm_blocks WHERE expires IS NULL OR expires>?', [now()])->fetchAll(PDO::FETCH_COLUMN));
    $top = q("SELECT ip, COUNT(*) c, COUNT(DISTINCT site_id) s, COUNT(DISTINCT tag) t, MIN(at) f, MAX(at) l FROM gm_requests WHERE tag<>'' AND at>? GROUP BY ip ORDER BY c DESC LIMIT 50", [ago($days * 86400)])->fetchAll(); ?>
<div class="tabs"><a class="<?= $days === 1 ? 'on' : '' ?>" href="?v=attackers">آخر 24 ساعة</a><a class="<?= $days === 7 ? 'on' : '' ?>" href="?v=attackers&d=7">آخر 7 أيام</a></div>
<section class="pn"><h2>المصادر الهجومية <small><?= count($top) ?> عنوان</small></h2>
<?php if (!$top): ?><div class="empty">لا توجد طلبات هجومية في هذه الفترة</div><?php else: ?><div class="ov"><table class="gr"><thead><tr><th>IP</th><th class="end">طلبات هجومية</th><th class="end hm">أنواع</th><th class="end hm">أصول</th><th class="hm">أول ظهور</th><th>آخر ظهور</th><th></th></tr></thead><tbody>
<?php foreach ($top as $t): ?><tr><td><?= ip_link($t['ip']) ?></td><td class="end num"><?= (int)$t['c'] ?></td><td class="end num hm"><?= (int)$t['t'] ?></td><td class="end num hm"><?= (int)$t['s'] ?></td><td class="nw num hm"><?= h($t['f']) ?></td><td class="nw num"><?= h($t['l']) ?></td>
<td class="end"><?= isset($blocked[$t['ip']]) ? '<span class="tag">محظور</span>' : f('block', 'حظر 24 ساعة', ['ip' => $t['ip'], 'scope' => 0, 'hours' => 24, 'reason' => 'مصدر هجومي'], 'sm dng') ?></td></tr><?php endforeach ?></tbody></table></div><?php endif ?></section>
<section class="pn"><h2>آخر الطلبات الهجومية</h2>
<?php $feed = q("SELECT * FROM gm_requests WHERE tag<>'' ORDER BY at DESC, id DESC LIMIT 80")->fetchAll();
if (!$feed): ?><div class="empty">لا توجد</div><?php else: ?><div class="ov"><table class="gr"><thead><tr><th>الوقت</th><th>IP</th><th>النوع</th><th class="hm">الأصل</th><th>الطلب</th></tr></thead><tbody>
<?php foreach ($feed as $r): ?><tr><td class="nw num"><?= h($r['at']) ?></td><td><?= ip_link($r['ip']) ?></td><td class="nw"><span class="tag"><?= h(GM_TAGS[$r['tag']] ?? $r['tag']) ?></span></td><td class="hm"><?= h($sites[$r['site_id']] ?? '?') ?></td>
<td><span class="mono"><?= h($r['method'] . ' ' . $r['path']) ?></span></td></tr><?php endforeach ?></tbody></table></div><?php endif ?></section><?php
}
function quarantine_table(array $qs, array $sites = []): string {
    if (!$qs) return '<div class="empty">الحجر فارغ</div>';
    $o = '<div class="ov"><table class="gr"><thead><tr><th>الملف</th>' . ($sites ? '<th>الأصل</th>' : '') . '<th>السبب</th><th>وقت العزل</th><th></th></tr></thead><tbody>';
    foreach ($qs as $x) {
        $o .= '<tr><td><span class="mono">' . h($x['path']) . '</span><div class="mono mut">sha256 ' . h(substr($x['sha256'], 0, 24)) . '…</div></td>' . ($sites ? '<td>' . h($sites[$x['site_id']] ?? '?') . '</td>' : '')
            . '<td>' . h($x['reason']) . ' <span class="tag">' . ($x['actor'] === 'auto' ? 'تلقائي' : 'يدوي') . '</span></td><td class="nw num">' . h($x['at']) . '</td><td class="end nw">';
        if ($x['state'] === 'held') $o .= '<a class="btn sm" href="?site=' . (int)$x['site_id'] . '&q=' . h($x['qname']) . '">عرض</a> ' . f('restore', 'إرجاع', ['qid' => $x['id']], 'sm', 'إرجاع الملف لمكانه الأصلي؟') . ' ' . f('qdel', 'حذف نهائي', ['qid' => $x['id']], 'sm dng', 'حذف نهائي؟ لا يمكن التراجع، وتفقد الدليل.');
        else $o .= '<span class="mut">' . ($x['state'] === 'restored' ? 'أُرجع' : 'حُذف') . '</span>';
        $o .= '</td></tr>';
    }
    return $o . '</tbody></table></div>';
}
function view_quarantine(): void {
    $sites = []; foreach (q('SELECT id, name FROM gm_sites') as $x) $sites[$x['id']] = $x['name'];
    $qs = q('SELECT * FROM gm_quarantine ORDER BY id DESC LIMIT 300')->fetchAll(); ?>
<section class="pn"><h2>الملفات المعزولة <small><?= count(array_filter($qs, fn($x) => $x['state'] === 'held')) ?> محجوز</small></h2><?= quarantine_table($qs, $sites) ?></section>
<p class="mut">الملف المعزول يُنقل خارج مساره بامتداد غير تنفيذي مع حفظ بصمته، فيبقى دليلاً يمكن إرجاعه.</p><?php
}

/* ================= صفحة الأصل ================= */
function view_site(array $s): void {
    $id = (int)$s['id'];
    $open = q('SELECT * FROM gm_issues WHERE site_id=? AND closed_at IS NULL ORDER BY id DESC', [$id])->fetchAll();
    $diff = $s['files_diff'] ? json_decode($s['files_diff'], true) : null;
    $tr = !empty($s['traffic_last']) ? json_decode($s['traffic_last'], true) : null;
    $au = json_decode($s['audit'] ?? '', true) ?: null;
    $sc = json_decode($s['scan'] ?? '', true) ?: null;
    $ign = json_decode($s['scan_ignore'] ?? '', true) ?: [];
    $hits = $sc ? array_values(array_filter($sc['hits'], fn($x) => !in_array($x[0], $ign, true))) : [];
    $ssl = $s['ssl_expires'] ? (int)floor((strtotime($s['ssl_expires']) - time()) / 86400) : null;
    $nFiles = $diff ? count($diff['added']) + count($diff['mod']) + count($diff['removed']) : 0;
    $tab = (string)($_GET['tab'] ?? ''); $tabs = ['' => 'ملخص', 'files' => 'الملفات', 'scan' => 'الفحص والتدقيق', 'attacks' => 'الهجمات', 'forensics' => 'التحقيق', 'setup' => 'الربط'];
    if (!isset($tabs[$tab])) $tab = '';
    $badge = ['' => count($open), 'files' => $nFiles, 'scan' => count(array_filter($hits, fn($x) => $x[1]))]; ?>
<section class="pn"><h2><span style="font-size:15px"><?= h($s['name']) ?></span> <a class="mono" href="<?= h($s['url']) ?>" target="_blank" rel="noopener noreferrer"><?= h(host_of($s['url'])) ?></a>
  <span class="sp acts"><?= score_bar($s['score']) ?> <?= lv_chip(site_level($s, $open)) ?></span></h2>
<div class="facts">
  <div><span>HTTP</span><b class="num"><?= h($s['http_code'] ?? '—') ?></b></div><div><span>زمن الاستجابة</span><b class="num"><?= $s['resp_ms'] === null ? '—' : '<bdi dir="ltr">' . (int)$s['resp_ms'] . ' ms</bdi>' ?></b></div>
  <div><span>شهادة SSL</span><b><?= $ssl === null ? '—' : 'باقي ' . $ssl . ' يوم' ?></b></div><div><span>الاتصال</span><b><?= conn_label($s) ?></b></div>
  <div><span>ملفات مراقَبة</span><b class="num"><?= $s['files_count'] === null ? '—' : (int)$s['files_count'] ?></b></div>
  <div><span>الحارس، طلبات / 5 د</span><b class="num"><?= $tr ? (int)$tr['total'] . (!empty($tr['blocked']) ? ' <small class="mut">(' . (int)$tr['blocked'] . ' محجوب)</small>' : '') : '<span class="mut">غير مربوط</span>' ?></b></div>
  <div><span>آخر فحص</span><b class="num"><?= h($s['last_check'] ?? '—') ?></b></div>
</div></section>
<div class="tabs"><?php foreach ($tabs as $k => $lb): ?><a class="<?= $tab === $k ? 'on' : '' ?>" href="?site=<?= $id ?><?= $k ? '&tab=' . $k : '' ?>"><?= $lb ?><?= !empty($badge[$k]) ? ' <b>' . $badge[$k] . '</b>' : '' ?></a><?php endforeach ?></div>

<?php if ($tab === ''): ?>
<section class="pn"><h2>التنبيهات المفتوحة <small><?= count($open) ?></small></h2><?= alerts_table($open, false, true) ?></section>
<section class="pn"><h2>إجراءات الاستجابة</h2><div class="pb acts">
  <?php if (has_agent($s)): ?><?= f('scan', 'فحص عميق للكود', ['id' => $id]) ?><?php endif ?><?= f('audit', 'تدقيق أمني', ['id' => $id]) ?>
  <a class="btn" href="?report=<?= $id ?>" target="_blank">تقرير الحادث</a>
  <?php if ($s['agent_url']): ?><?= $s['lockdown'] ? f('unlock', 'فتح الموقع', ['id' => $id], 'pri') : f('lock', 'إغلاق طارئ', ['id' => $id], 'dng', 'سيُغلق الموقع أمام كل الزوار عدا العناوين المستثناة. متأكد؟') ?><?php endif ?>
  <?= f('ok_page', 'اعتماد الصفحة و DNS', ['id' => $id]) ?>
</div></section>

<?php elseif ($tab === 'files'): ?>
<section class="pn"><h2>تغييرات غير معتمدة <small><?= $nFiles ?> ملف</small></h2>
<?php if (!$diff): ?><div class="empty">الملفات مطابقة للبصمة المعتمدة</div><?php else: ?>
<form method="post" onsubmit="return confirm('عزل الملفات المحددة؟ ستُنقل إلى الحجر ويمكن إرجاعها.')"><?= csrf_in() ?><input type="hidden" name="id" value="<?= $id ?>">
<div class="ov"><table class="gr"><thead><tr><th></th><th>التغيير</th><th>الملف</th><th></th></tr></thead><tbody>
<?php foreach (CHG_NAME as $k => $lbl) foreach (array_slice($diff[$k], 0, 200) as $p): $hot = in_array($p, $diff['strong'] ?? [], true); $sus = $diff['sus'][$p] ?? null; ?>
<tr class="<?= $hot ? 'r-crit' : ($sus ? 'r-med' : '') ?>"><td class="sev"><?php if ($k !== 'removed'): ?><input type="checkbox" name="paths[]" value="<?= h($p) ?>" <?= $hot ? 'checked' : '' ?> aria-label="تحديد"><?php endif ?></td>
<td class="nw"><span class="tag"><?= $lbl ?></span></td><td><span class="mono"><?= h($p) ?></span><?= $sus ? '<div class="msg">' . ($hot ? 'توقيع خبيث: ' : 'مؤشر: ') . h(implode('، ', $sus)) . '</div>' : '' ?></td>
<td class="end"><?php if ($k !== 'removed'): ?><a class="btn sm" href="?site=<?= $id ?>&file=<?= urlencode($p) ?>">عرض</a><?php endif ?></td></tr><?php endforeach ?></tbody></table></div>
<div class="pb acts"><button class="btn dng" name="act" value="quarantine">عزل المحدد</button></div></form>
<div class="pb acts" style="border-top:1px solid var(--ln)"><?= f('ok_files', 'كل التغييرات مني، اعتمدها', ['id' => $id], 'pri', 'متأكد أن كل التغييرات منك؟ ستُعتمد الملفات الحالية كأساس.') ?>
<span class="mut">الملف المعدّل لا تُسترجع نسخته الأصلية من هنا، استرجعها من نسخة احتياطية.</span></div><?php endif ?></section>
<section class="pn"><h2>الحجر</h2><?= quarantine_table(q('SELECT * FROM gm_quarantine WHERE site_id=? ORDER BY id DESC LIMIT 100', [$id])->fetchAll()) ?></section>

<?php elseif ($tab === 'scan'): ?>
<section class="pn"><h2>الفحص العميق <small><?= !$sc ? 'لم يُجرَ بعد' : (empty($sc['done']) ? 'جارٍ…' : 'فُحص ' . (int)$sc['scanned'] . ' ملف، ' . h($sc['at'] ?? '')) ?></small><?php if (has_agent($s)): ?><span class="sp"><?= f('scan', 'افحص الآن', ['id' => $id], 'sm') ?></span><?php endif ?></h2>
<?php if (!$hits): ?><div class="empty"><?= $sc ? 'لا توجد نتائج مشبوهة' : 'يعمل تلقائياً مرة يومياً بعد ربط الوكيل' ?></div><?php else: ?><div class="ov"><table class="gr"><thead><tr><th>الثقة</th><th>الملف</th><th></th></tr></thead><tbody>
<?php foreach (array_slice($hits, 0, 200) as $x): ?><tr class="<?= $x[1] ? 'r-crit' : 'r-med' ?>"><td class="sev"><?= $x[1] ? sev_chip('crit') : sev_chip('med') ?></td>
<td><span class="mono"><?= h($x[0]) ?></span><div class="msg"><?= h(implode('، ', array_merge($x[1], $x[2]))) ?></div></td>
<td class="end nw"><a class="btn sm" href="?site=<?= $id ?>&file=<?= urlencode($x[0]) ?>">عرض</a> <?= f('quarantine', 'عزل', ['id' => $id, 'paths[]' => $x[0], 'reason' => 'الفحص العميق: ' . implode('، ', array_merge($x[1], $x[2]))], 'sm dng', 'عزل هذا الملف؟') ?> <?= f('ignore', 'تجاهل', ['id' => $id, 'path' => $x[0]], 'sm') ?></td></tr><?php endforeach ?></tbody></table></div>
<div class="pb mut">«حرج» = توقيع خبيث مؤكد. «متوسط» = مؤشر يظهر أحياناً في مكتبات سليمة، اعرض الملف قبل العزل.</div><?php endif ?></section>
<section class="pn"><h2>التدقيق الأمني <small><?= $au ? count($au['findings']) . ' ملاحظة، ' . h($s['audit_at']) : 'لم يُجرَ بعد' ?></small><span class="sp"><?= f('audit', 'دقّق الآن', ['id' => $id], 'sm') ?></span></h2>
<?php if ($au && !empty($au['info'])): ?><div class="facts"><div><span>PHP</span><b class="mono"><?= h($au['info']['php']) ?></b></div><div><span>الخادم</span><b class="mono"><?= h($au['info']['server'] ?: '—') ?></b></div>
<div><span>إجمالي الملفات</span><b class="num"><?= (int)$au['info']['files'] ?></b></div><div><span>تغيّرت خلال 48 ساعة</span><b class="num"><?= (int)$au['info']['recent48h'] ?></b></div></div><?php endif ?>
<?php if (!$au || !$au['findings']): ?><div class="empty"><?= $au ? 'لا توجد ملاحظات' : 'يعمل تلقائياً مرة يومياً' ?></div><?php else: ?><table class="gr"><thead><tr><th>الخطورة</th><th>الملاحظة والحل</th></tr></thead><tbody>
<?php foreach ($au['findings'] as $x): $k = ['high' => 'crit', 'med' => 'med', 'low' => 'low'][$x[0]]; ?><tr class="r-<?= $k ?>"><td class="sev"><?= sev_chip($k) ?></td><td><b><?= h($x[1]) ?></b><div class="msg"><?= h($x[2]) ?></div></td></tr><?php endforeach ?></tbody></table><?php endif ?></section>

<?php elseif ($tab === 'attacks'):
    $hours = []; foreach (q("SELECT SUBSTR(at,1,13) h, COUNT(*) c FROM gm_requests WHERE site_id=? AND tag<>'' AND at>? GROUP BY h", [$id, ago(86400)]) as $r) $hours[$r['h']] = $r['c'];
    $atk = q("SELECT ip, tag, COUNT(*) c, MAX(at) l FROM gm_requests WHERE site_id=? AND tag<>'' AND at>? GROUP BY ip, tag ORDER BY c DESC LIMIT 40", [$id, ago(86400)])->fetchAll(); ?>
<?php if (!$tr): ?><div class="note">الحارس غير مربوط بهذا الأصل، فلا يوجد عدّ للطلبات ولا كشف للهجمات. الخطوات في تبويب «الربط».</div><?php endif ?>
<section class="pn"><h2>الطلبات الهجومية لكل ساعة <small>آخر 24 ساعة</small></h2><div class="pb"><?= chart_hours($hours, 'طلب هجومي') ?></div></section>
<div class="g2"><section class="pn"><h2>المهاجمون <small>24 ساعة</small></h2>
<?php if (!$atk): ?><div class="empty">لا توجد هجمات مسجّلة</div><?php else: ?><div class="ov"><table class="gr"><thead><tr><th>IP</th><th>النوع</th><th class="end">العدد</th><th class="hm">آخر مرة</th><th></th></tr></thead><tbody>
<?php foreach ($atk as $a): ?><tr><td><?= ip_link($a['ip']) ?></td><td><span class="tag"><?= h(GM_TAGS[$a['tag']] ?? $a['tag']) ?></span></td><td class="end num"><?= (int)$a['c'] ?></td><td class="hm nw num"><?= h($a['l']) ?></td>
<td class="end"><?= f('block', 'حظر', ['ip' => $a['ip'], 'scope' => $id, 'hours' => 24, 'reason' => 'هجوم: ' . (GM_TAGS[$a['tag']] ?? $a['tag'])], 'sm dng') ?></td></tr><?php endforeach ?></tbody></table></div><?php endif ?></section>
<section class="pn"><h2>أكثر المسارات طلباً <small>آخر 5 دقائق</small></h2><div class="pb"><?= hbars($tr['paths'] ?? []) ?></div></section></div>
<?php if ($tr && !empty($tr['ips'])): ?><section class="pn"><h2>أكثر العناوين نشاطاً <small>آخر 5 دقائق، <?= (int)$tr['uniq'] ?> عنوان</small></h2><table class="gr"><tbody>
<?php foreach ($tr['ips'] as $k => $c): ?><tr><td><?= ip_link((string)$k) ?></td><td class="end num"><?= (int)$c ?> طلب</td></tr><?php endforeach ?></tbody></table></section><?php endif ?>

<?php elseif ($tab === 'forensics'): $hrs = (int)($_GET['hours'] ?? 0); ?>
<section class="pn"><h2>ملفات تغيّرت مؤخراً <small>حسب ctime، كل أنواع الملفات</small></h2><div class="pb">
<?php if (!has_agent($s)): ?><span class="mut">يحتاج وكيلاً أو اتصال SSH.</span><?php else: ?>
<form method="get" class="acts"><input type="hidden" name="site" value="<?= $id ?>"><input type="hidden" name="tab" value="forensics">
<select name="hours"><?php foreach ([1 => 'آخر ساعة', 6 => 'آخر 6 ساعات', 24 => 'آخر 24 ساعة', 72 => 'آخر 3 أيام', 168 => 'آخر أسبوع', 720 => 'آخر 30 يوم'] as $k => $v): ?><option value="<?= $k ?>" <?= ($hrs ?: 24) === $k ? 'selected' : '' ?>><?= $v ?></option><?php endforeach ?></select><button class="btn pri">ابحث</button>
<span class="mut">ctime لا يتغيّر بأمر touch، فاختلافه الكبير عن mtime مؤشر على تزوير التاريخ.</span></form><?php endif ?></div>
<?php if ($hrs && has_agent($s)): $t = agent_call($s, 'timeline', ['hours' => $hrs]);
  if (!$t): ?><div class="empty">تعذر الاتصال بالموقع</div><?php elseif (!$t['files']): ?><div class="empty">لا توجد ملفات تغيّرت في هذه الفترة</div><?php else: ?>
<div class="ov"><table class="gr"><thead><tr><th>الملف</th><th>ctime</th><th>mtime</th><th class="end hm">الحجم</th><th class="hm">صلاحيات</th></tr></thead><tbody>
<?php foreach ($t['files'] as $x): $fake = abs($x[3] - $x[2]) > 86400; ?><tr class="<?= $fake ? 'r-med' : '' ?>"><td class="sev"><a class="mono" href="?site=<?= $id ?>&file=<?= urlencode($x[0]) ?>"><?= h($x[0]) ?></a></td>
<td class="nw num"><?= date('Y-m-d H:i:s', $x[3]) ?></td><td class="nw num"><?= date('Y-m-d H:i', $x[2]) ?><?= $fake ? ' <span class="tag">تاريخ مختلف</span>' : '' ?></td><td class="end num hm"><?= (int)$x[1] ?></td><td class="mono hm"><?= h($x[4]) ?></td></tr><?php endforeach ?></tbody></table></div>
<?php endif; endif ?></section>
<section class="pn"><h2>الخط الزمني</h2><?php $ev = [];
foreach (q('SELECT * FROM gm_issues WHERE site_id=? ORDER BY id DESC LIMIT 80', [$id]) as $i) {
    $ev[] = [$i['opened_at'], 'تنبيه', 'بدأ: ' . GM_TYPES[$i['type']][1]];
    if ($i['closed_at']) $ev[] = [$i['closed_at'], 'تنبيه', 'انتهى: ' . GM_TYPES[$i['type']][1]];
}
foreach (q('SELECT * FROM gm_filelog WHERE site_id=? ORDER BY id DESC LIMIT 150', [$id]) as $x) $ev[] = [$x['at'], 'ملف ' . CHG_NAME[$x['chg']], $x['path'] . ($x['sus'] ? ' — ' . $x['sus'] : '')];
foreach (q('SELECT * FROM gm_actions WHERE site_id=? ORDER BY id DESC LIMIT 80', [$id]) as $x) $ev[] = [$x['at'], 'إجراء ' . ($x['actor'] === 'auto' ? 'تلقائي' : 'يدوي'), $x['action'] . ': ' . $x['detail']];
usort($ev, fn($a, $b) => strcmp($b[0], $a[0]));
if (!$ev): ?><div class="empty">لا توجد أحداث بعد</div><?php else: ?><div class="ov"><table class="gr"><tbody>
<?php foreach (array_slice($ev, 0, 250) as $e): ?><tr><td class="nw num mut"><?= h($e[0]) ?></td><td class="nw"><span class="tag"><?= h($e[1]) ?></span></td><td style="word-break:break-word"><?= h($e[2]) ?></td></tr><?php endforeach ?></tbody></table></div><?php endif ?></section>

<?php else: ?>
<section class="pn"><h2>الاتصال بالأصل</h2><div class="pb">
<?php if ($s['ssh_host']): ?><p>الملفات تُفحص عبر SSH: <span class="mono"><?= h($s['ssh_user'] . '@' . $s['ssh_host'] . ':' . $s['ssh_port']) ?></span> على المسار <span class="mono"><?= h($s['ssh_path']) ?></span></p><p><?= f('sshtest', 'اختبار اتصال SSH', ['id' => $id], 'pri') ?></p><?php endif ?>
<?php if ($s['agent_url']): ?><p>1. نزّل ملف الوكيل (نفس الملف لكل المواقع) وارفعه إلى المجلد العام باسم <code>gm-agent.php</code>.</p><p><a class="btn pri" href="?agent=<?= $id ?>">تنزيل gm-agent.php</a></p>
<p>2. اربط الحارس حتى يعمل عدّ الطلبات وكشف الهجمات والحظر والإغلاق الطارئ:</p>
<p><b>Laravel:</b> بعد <code>&lt;?php</code> في <code>public/index.php</code> أضف <code>require_once __DIR__.'/gm-agent.php';</code></p>
<p><b>PHP عادي:</b> نفس السطر أعلى <code>index.php</code>، أو في <code>.user.ini</code>: <code>auto_prepend_file = "/المسار/الكامل/gm-agent.php"</code></p>
<p class="mut">بعد التعديل يصلك تنبيه «تغيير في الملفات» مرة واحدة. اعتمده من تبويب الملفات.</p><?php endif ?>
<?php if (!$s['agent_url']): ?><p>الحارس غير مفعّل لهذا الأصل: لا يوجد عدّ للطلبات ولا كشف هجمات ولا حظر ولا إغلاق طارئ.</p><p><?= f('mkagent', 'تفعيل ملف الحارس', ['id' => $id]) ?></p><?php endif ?>
<?php if (!has_agent($s)): ?><p class="mut">هذا الأصل يُراقَب من الخارج فقط. احذفه وأضفه من جديد مع تفعيل الوكيل أو SSH لتفعيل فحص الملفات.</p><?php endif ?></div></section>
<section class="pn"><h2>منطقة الخطر</h2><div class="pb acts"><?= f('del', 'حذف الأصل وكل سجلاته', ['id' => $id], 'dng', 'حذف الموقع وكل سجلاته من المراقبة؟') ?></div></section>
<?php endif;
}

/* ================= عارض الملفات ================= */
function view_file(array $s, string $path, string $qn): void {
    $id = (int)$s['id'];
    $j = agent_call($s, 'get', $qn !== '' ? ['q' => $qn] : ['path' => $path]);
    echo '<p><a href="?site=' . $id . '&tab=files">رجوع إلى ' . h($s['name']) . '</a></p>';
    if (!$j || empty($j['found'])) { echo '<section class="pn"><div class="empty">تعذر قراءة الملف: غير موجود، أو نوعه غير مسموح بعرضه، أو الاتصال بالأصل مقطوع.</div></section>'; return; }
    $src = (string)base64_decode($j['b64']);
    if (!mb_check_encoding($src, 'UTF-8')) $src = preg_replace('~[^\x09\x0A\x20-\x7E]~', '·', $src);
    $Q = $qn !== '' ? q('SELECT * FROM gm_quarantine WHERE site_id=? AND qname=?', [$id, $qn])->fetch() : null; ?>
<section class="pn"><h2><span class="mono" style="font-size:13.5px"><?= h($j['path']) ?></span><?= $qn !== '' ? ' <span class="tag">في الحجر</span>' : '' ?>
<span class="sp acts"><?php if ($qn === ''): ?><?= f('quarantine', 'عزل هذا الملف', ['id' => $id, 'paths[]' => $j['path'], 'reason' => 'عزل يدوي من عارض الملفات'], 'dng', 'عزل هذا الملف؟') ?>
<?php elseif ($Q && $Q['state'] === 'held'): ?><?= f('restore', 'إرجاع', ['qid' => $Q['id']], '', 'إرجاع الملف لمكانه الأصلي؟') ?><?= f('qdel', 'حذف نهائي', ['qid' => $Q['id']], 'dng', 'حذف نهائي؟') ?><?php endif ?></span></h2>
<div class="facts"><div><span>الحجم</span><b class="num"><?= (int)$j['size'] ?> بايت</b></div><div><span>mtime</span><b class="num"><?= date('Y-m-d H:i:s', $j['mtime']) ?></b></div>
<div><span>ctime</span><b class="num"><?= date('Y-m-d H:i:s', $j['ctime']) ?></b></div><div><span>الصلاحيات</span><b class="mono"><?= h($j['perms']) ?></b></div></div>
<div class="pb"><div class="mut">MD5</div><div class="mono"><?= h($j['md5']) ?></div><div class="mut" style="margin-top:6px">SHA-256</div><div class="mono"><?= h($j['sha256']) ?></div>
<p><a href="https://www.virustotal.com/gui/search/<?= h($j['sha256']) ?>" target="_blank" rel="noopener noreferrer">ابحث عن البصمة في VirusTotal</a></p></div>
<?php if ($j['hits']['s'] || $j['hits']['w']): ?><table class="gr"><tbody>
<?php foreach ($j['hits']['s'] as $x): ?><tr class="r-crit"><td class="sev"><?= sev_chip('crit') ?></td><td><?= h($x) ?></td></tr><?php endforeach ?>
<?php foreach ($j['hits']['w'] as $x): ?><tr class="r-med"><td class="sev"><?= sev_chip('med') ?></td><td><?= h($x) ?></td></tr><?php endforeach ?></tbody></table><?php endif ?></section>
<pre class="src"><?php $re = '~eval\s*\(|base64_decode|gzinflate|gzuncompress|str_rot13|shell_exec|passthru|system\s*\(|proc_open|popen|assert\s*\(|\$_(POST|GET|REQUEST|COOKIE)|move_uploaded_file|auto_prepend_file~i';
foreach (explode("\n", $src) as $n => $line) echo '<span' . (preg_match($re, $line) ? ' class="hot"' : '') . '><i>' . ($n + 1) . '</i>' . h(mb_substr($line, 0, 2000)) . "</span>";
?></pre><?php if ($j['size'] > 204800): ?><p class="mut">عُرض أول 200KB فقط.</p><?php endif;
}

/* ================= تحقيق IP ================= */
function view_ip(string $ip): void {
    $sites = []; foreach (q('SELECT id, name FROM gm_sites ORDER BY id') as $x) $sites[$x['id']] = $x['name'];
    $st = q("SELECT COUNT(*) c, SUM(CASE WHEN tag<>'' THEN 1 ELSE 0 END) a, MIN(at) f, MAX(at) l FROM gm_requests WHERE ip=?", [$ip])->fetch();
    $bySite = q("SELECT site_id, COUNT(*) c, SUM(CASE WHEN tag<>'' THEN 1 ELSE 0 END) a FROM gm_requests WHERE ip=? GROUP BY site_id ORDER BY c DESC", [$ip])->fetchAll();
    $types = []; foreach (q("SELECT tag, COUNT(*) c FROM gm_requests WHERE ip=? AND tag<>'' GROUP BY tag ORDER BY c DESC", [$ip]) as $r) $types[GM_TAGS[$r['tag']] ?? $r['tag']] = $r['c'];
    $uas = q('SELECT ua, COUNT(*) c FROM gm_requests WHERE ip=? GROUP BY ua ORDER BY c DESC LIMIT 6', [$ip])->fetchAll();
    $blocks = q('SELECT * FROM gm_blocks WHERE ip=? AND (expires IS NULL OR expires>?)', [$ip, now()])->fetchAll(); ?>
<section class="pn"><h2><span class="mono" style="font-size:15px"><?= h($ip) ?></span><?= $blocks ? ' <span class="tag">محظور</span>' : '' ?>
<span class="sp acts"><a class="btn sm" href="https://www.abuseipdb.com/check/<?= h($ip) ?>" target="_blank" rel="noopener noreferrer">AbuseIPDB</a><a class="btn sm" href="https://ipinfo.io/<?= h($ip) ?>" target="_blank" rel="noopener noreferrer">ipinfo</a></span></h2>
<div class="facts"><div><span>طلبات مسجّلة</span><b class="num"><?= (int)$st['c'] ?></b></div><div><span>منها هجومية</span><b class="num"><?= (int)$st['a'] ?></b></div>
<div><span>أول ظهور</span><b class="num"><?= h($st['f'] ?? '—') ?></b></div><div><span>آخر ظهور</span><b class="num"><?= h($st['l'] ?? '—') ?></b></div></div>
<?php foreach ($blocks as $b): ?><div class="pb acts" style="border-top:1px solid var(--ln)"><span>محظور على <?= $b['site_id'] ? h($sites[$b['site_id']] ?? '?') : 'كل الأصول' ?> حتى <?= h($b['expires'] ?? 'إشعار آخر') ?>، السبب: <?= h($b['reason']) ?></span><?= f('unblock', 'رفع الحظر', ['bid' => $b['id']], 'sm') ?></div><?php endforeach ?>
<div class="pb" style="border-top:1px solid var(--ln)"><form method="post" class="acts"><?= csrf_in() ?><input type="hidden" name="ip" value="<?= h($ip) ?>">
<select name="scope"><option value="0">كل الأصول</option><?php foreach ($sites as $k => $v): ?><option value="<?= $k ?>"><?= h($v) ?></option><?php endforeach ?></select>
<select name="hours"><option value="1">ساعة</option><option value="24" selected>24 ساعة</option><option value="168">أسبوع</option><option value="720">30 يوم</option><option value="0">دائم</option></select>
<input type="text" name="reason" placeholder="سبب الحظر" style="width:auto;flex:1;min-width:130px"><button class="btn dng" name="act" value="block">حظر العنوان</button></form></div></section>
<div class="g2"><section class="pn"><h2>النشاط حسب الأصل</h2><?php if (!$bySite): ?><div class="empty">لا توجد طلبات مسجّلة لهذا العنوان</div><?php else: ?><table class="gr"><thead><tr><th>الأصل</th><th class="end">طلبات</th><th class="end">هجومية</th></tr></thead><tbody>
<?php foreach ($bySite as $x): ?><tr><td><a href="?site=<?= (int)$x['site_id'] ?>&tab=attacks"><?= h($sites[$x['site_id']] ?? '?') ?></a></td><td class="end num"><?= (int)$x['c'] ?></td><td class="end num"><?= (int)$x['a'] ?></td></tr><?php endforeach ?></tbody></table>
<table class="gr"><thead><tr><th>User-Agent</th><th class="end">طلبات</th></tr></thead><tbody><?php foreach ($uas as $x): ?><tr><td><span class="mono"><?= h($x['ua'] ?: '(فارغ)') ?></span></td><td class="end num"><?= (int)$x['c'] ?></td></tr><?php endforeach ?></tbody></table><?php endif ?></section>
<section class="pn"><h2>أنواع هجماته</h2><div class="pb"><?= hbars($types) ?></div></section></div>
<section class="pn"><h2>آخر 300 طلب <small>تُحفظ الطلبات الهجومية وغير GET وعيّنة من الباقي لمدة <?= (int)setting('keep_days', 7) ?> أيام</small></h2><div class="ov"><table class="gr"><thead><tr><th>الوقت</th><th class="hm">الأصل</th><th>الطلب</th><th>التصنيف</th></tr></thead><tbody>
<?php foreach (q('SELECT * FROM gm_requests WHERE ip=? ORDER BY at DESC, id DESC LIMIT 300', [$ip]) as $r): ?>
<tr class="<?= $r['tag'] ? 'r-high' : '' ?>"><td class="sev nw num"><?= h($r['at']) ?></td><td class="hm"><?= h($sites[$r['site_id']] ?? '?') ?></td><td><span class="mono"><?= h($r['method'] . ' ' . $r['path']) ?></span></td><td class="nw"><?= $r['tag'] ? '<span class="tag">' . h(GM_TAGS[$r['tag']] ?? $r['tag']) . '</span>' : '' ?></td></tr>
<?php endforeach ?></tbody></table></div></section><?php
}

/* ================= الإعدادات والسجل ================= */
function view_settings(): void { $v = fn($k, $d) => (int)setting($k, $d); ?>
<div class="g2" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
<section class="pn"><h2>سياسة الكشف والاستجابة</h2><div class="pb"><form method="post"><?= csrf_in() ?><input type="hidden" name="act" value="policy">
<label class="ck"><input type="checkbox" name="auto_block" <?= setting('auto_block') === '1' ? 'checked' : '' ?>> حظر تلقائي لأي عنوان يهاجم أو يجرّب كلمات السر أو يغرق الموقع</label>
<label class="ck"><input type="checkbox" name="auto_quarantine" <?= setting('auto_quarantine') === '1' ? 'checked' : '' ?>> عزل تلقائي للملفات الجديدة التي تحمل توقيعاً خبيثاً مؤكداً</label>
<label class="ck"><input type="checkbox" name="auto_plant" <?= setting('auto_plant') === '1' ? 'checked' : '' ?>> زرع ملف الوكيل تلقائياً في كل الأصول المربوطة بـ SSH</label>
<label>مدة الحظر التلقائي (ساعات)</label><input type="text" name="block_hours" value="<?= $v('block_hours', 24) ?>" dir="ltr">
<label>عناوين مستثناة من الحظر والإغلاق، واحد بكل سطر. عنوانك الحالي: <span class="mono"><?= h($_SERVER['REMOTE_ADDR'] ?? '') ?></span></label><textarea name="allow_ips" rows="3" dir="ltr"><?= h(setting('allow_ips', '')) ?></textarea>
<label>تنبيه هجوم: طلبات هجومية من عنوان واحد خلال 5 دقائق</label><input type="text" name="atk_min" value="<?= $v('atk_min', 5) ?>" dir="ltr">
<label>تنبيه إغراق: إجمالي طلبات الأصل خلال 5 دقائق (ويكون 4 أضعاف المعدل)</label><input type="text" name="rq_min" value="<?= $v('rq_min', 500) ?>" dir="ltr">
<label>طلبات من عنوان واحد خلال 5 دقائق</label><input type="text" name="ip_max" value="<?= $v('ip_max', 300) ?>" dir="ltr">
<label>محاولات دخول من عنوان واحد خلال 5 دقائق</label><input type="text" name="login_max" value="<?= $v('login_max', 20) ?>" dir="ltr">
<label>فحص ملفات الأصول المربوطة بـ SSH كل (دقائق). التوقف والتشويه يُفحصان كل 5 دقائق دائماً</label><input type="text" name="files_every" value="<?= $v('files_every', 30) ?>" dir="ltr">
<label>مدة حفظ سجل الطلبات (أيام)</label><input type="text" name="keep_days" value="<?= $v('keep_days', 7) ?>" dir="ltr">
<p><button class="btn pri">حفظ السياسة</button></p></form></div></section>
<div>
<section class="pn"><h2>تنبيهات تيليگرام</h2><div class="pb"><form method="post"><?= csrf_in() ?><input type="hidden" name="act" value="settings">
<label>Bot Token من @BotFather</label><input type="text" name="tg_token" value="<?= h(setting('tg_token', '')) ?>" dir="ltr">
<label>Chat ID (رقمك أو رقم الكروب)</label><input type="text" name="tg_chat" value="<?= h(setting('tg_chat', '')) ?>" dir="ltr">
<p><button class="btn pri">حفظ وإرسال تجربة</button></p></form></div></section>
<section class="pn"><h2>ملف الوكيل الموحّد</h2><div class="pb"><p>ملف واحد لكل مواقعك. لا يحتوي أي سر، ويستجيب فقط لطلبات موقّعة من هذه اللوحة.</p><p><a class="btn pri" href="?agent=0">تنزيل gm-agent.php</a></p>
<p class="mut">ارفعه إلى المجلد العام لكل موقع، أو فعّل «زرع ملف الوكيل تلقائياً» ليُزرع عبر SSH.</p></div></section>
<?php $pk = ssh_pubkey(); ?><section class="pn"><h2>مفتاح SSH للمراقب</h2><div class="pb">
<?php if ($pk): ?><p>أضف هذا المفتاح العام إلى SSH Keys في لوحة كل استضافة تريد ربطها:</p><textarea rows="3" dir="ltr" readonly onclick="this.select()"><?= h($pk) ?></textarea>
<p class="mut">المفتاح الخاص محفوظ في <span class="mono"><?= h(ssh_key_path()) ?></span>. من يملكه يدخل كل استضافاتك.</p>
<?php else: ?><p class="mut">لا يوجد مفتاح بعد. أنشئه مرة واحدة ثم أضف مفتاحه العام للاستضافات.</p><?= f('sshkey', 'إنشاء مفتاح', [], 'pri') ?><?php endif ?></div></section>
<section class="pn"><h2>كلمة المرور</h2><div class="pb"><form method="post"><?= csrf_in() ?><input type="hidden" name="act" value="passwd">
<label>الحالية</label><input type="password" name="old" required><label>الجديدة (10 أحرف فأكثر)</label><input type="password" name="new" minlength="10" required>
<p><button class="btn">تغيير كلمة المرور</button></p></form></div></section></div></div>
<?php $sites = []; foreach (q('SELECT id, name FROM gm_sites') as $x) $sites[$x['id']] = $x['name'];
$bl = q('SELECT * FROM gm_blocks WHERE expires IS NULL OR expires>? ORDER BY id DESC LIMIT 300', [now()])->fetchAll(); ?>
<section class="pn"><h2>العناوين المحظورة <small><?= count($bl) ?>، تُطبَّق على الأصول المربوط بها الحارس</small></h2>
<?php if (!$bl): ?><div class="empty">لا توجد عناوين محظورة</div><?php else: ?><div class="ov"><table class="gr"><thead><tr><th>IP</th><th>النطاق</th><th>السبب</th><th>حتى</th><th></th></tr></thead><tbody>
<?php foreach ($bl as $b): ?><tr><td><?= ip_link($b['ip']) ?></td><td><?= $b['site_id'] ? h($sites[$b['site_id']] ?? '?') : 'كل الأصول' ?></td><td><?= h($b['reason']) ?> <span class="tag"><?= $b['actor'] === 'auto' ? 'تلقائي' : 'يدوي' ?></span></td>
<td class="nw num"><?= h($b['expires'] ?? 'دائم') ?></td><td class="end"><?= f('unblock', 'رفع الحظر', ['bid' => $b['id']], 'sm') ?></td></tr><?php endforeach ?></tbody></table></div><?php endif ?>
<div class="pb" style="border-top:1px solid var(--ln)"><form method="post" class="acts"><?= csrf_in() ?><input type="hidden" name="scope" value="0"><input type="hidden" name="hours" value="0">
<input type="text" name="ip" placeholder="IP" dir="ltr" style="width:auto;flex:1;min-width:130px"><input type="text" name="reason" placeholder="السبب" style="width:auto;flex:1;min-width:130px"><button class="btn dng" name="act" value="block">حظر دائم على كل الأصول</button></form></div></section><?php
}
function view_log(): void {
    $sites = []; foreach (q('SELECT id, name FROM gm_sites') as $x) $sites[$x['id']] = $x['name'];
    $rows = q('SELECT * FROM gm_actions ORDER BY id DESC LIMIT 300')->fetchAll(); ?>
<section class="pn"><h2>الإجراءات اليدوية والتلقائية <small>آخر 300</small></h2>
<?php if (!$rows): ?><div class="empty">لا توجد إجراءات بعد</div><?php else: ?><div class="ov"><table class="gr"><thead><tr><th>الوقت</th><th>المنفّذ</th><th>الإجراء</th><th class="hm">الأصل</th><th>التفاصيل</th></tr></thead><tbody>
<?php foreach ($rows as $a): ?><tr><td class="nw num"><?= h($a['at']) ?></td><td><span class="tag"><?= $a['actor'] === 'auto' ? 'تلقائي' : 'يدوي' ?></span></td><td class="mono"><?= h($a['action']) ?></td>
<td class="hm"><?= $a['site_id'] ? h($sites[$a['site_id']] ?? '?') : '—' ?></td><td style="word-break:break-word"><?= h($a['detail']) ?></td></tr><?php endforeach ?></tbody></table></div><?php endif ?></section><?php
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
