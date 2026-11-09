-- الأدوار بمبدأ أقل صلاحية. الصلاحيات تُفحص في الخلفية لكل طلب.
INSERT INTO admin_roles (name, label_ar, label_en, permissions) VALUES
('super_admin', 'مشرف أعلى', 'Super Administrator', ARRAY[
  'dashboard.view','search.view','search.manage','search.test','crawler.view','crawler.control','crawler.manage',
  'index.view','index.manage','images.view','images.manage','ai.view','ai.manage','security.view','security.manage',
  'audit.view','analytics.view','admins.view','admins.manage','infra.view','infra.control','settings.view','settings.manage']),
('system_admin', 'مدير النظام', 'System Administrator', ARRAY[
  'dashboard.view','search.view','crawler.view','index.view','images.view','ai.view','ai.manage',
  'analytics.view','infra.view','infra.control','settings.view','settings.manage','security.view']),
('search_manager', 'مدير البحث', 'Search Manager', ARRAY[
  'dashboard.view','search.view','search.manage','search.test','index.view','images.view','analytics.view']),
('crawler_manager', 'مدير الزاحف', 'Crawler Manager', ARRAY[
  'dashboard.view','crawler.view','crawler.control','crawler.manage','index.view','images.view']),
('security_admin', 'مسؤول الأمن', 'Security Administrator', ARRAY[
  'dashboard.view','security.view','security.manage','audit.view','admins.view','analytics.view','infra.view']),
('auditor', 'مدقق (قراءة فقط)', 'Read-only Auditor', ARRAY[
  'dashboard.view','search.view','crawler.view','index.view','images.view','ai.view','security.view',
  'audit.view','analytics.view','admins.view','infra.view','settings.view']);

INSERT INTO index_versions (label, analyzer_version, status, notes, activated_at)
VALUES ('v1', 1, 'active', 'الإصدار الأول', now());

INSERT INTO system_settings (key, value) VALUES
('search.enabled',        'true'),
('search.image_enabled',  'true'),
('search.safe_default',   '"moderate"'),
('search.ranking', '{"text": 1.0, "title": 2.0, "authority": 1.5, "quality": 1.0, "freshness": 0.5, "iraqi": 0.6, "language": 0.4, "spam_penalty": 3.0}'),
('search.region_priority', '{"iq": 1.0, "arab": 0.3, "global": 0.0}'),
('search.per_domain_limit', '3'),
('crawler.state',         '"running"'),
('crawler.concurrency',   '8'),
('crawler.default_depth', '3'),
('crawler.max_page_bytes', '5000000'),
('crawler.allowed_ports', '[80, 443]'),
('crawler.user_agent',    '"SumerBot/1.0 (+https://sumer.iq/bot)"'),
('retention.crawl_logs_days',     '30'),
('retention.security_events_days','90'),
('retention.audit_logs_days',     '365'),
('retention.ops_metrics_days',    '400'),
('retention.temp_files_minutes',  '10'),
('ratelimit.search_per_minute',   '60'),
('ratelimit.upload_per_minute',   '10'),
('ratelimit.admin_login_per_15m', '10'),
('site.name_ar',          '"سومر"'),
('site.name_en',          '"Sumer"'),
('site.tagline_ar',       '"محرك بحث عراقي مستقل. يفهم لهجتك، ولا يعرف من أنت."'),
('site.tagline_en',       '"An independent Iraqi search engine. It understands you, and never knows who you are."'),
('site.logo_path',        'null'),
('site.default_lang',     '"ar"'),
('site.default_theme',    '"system"'),
('site.maintenance',      'false'),
('site.announcement',     '{"enabled": false, "ar": "", "en": ""}');
