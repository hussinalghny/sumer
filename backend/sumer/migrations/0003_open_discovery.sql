-- الاكتشاف التلقائي للويب: ميزانية زحف لكل موقع، وتتبع مصدر اكتشاف النطاق، وفهرس لعدّ المهام المعلّقة لكل نطاق.
ALTER TABLE domains ADD COLUMN budget_auto BOOLEAN NOT NULL DEFAULT TRUE;   -- FALSE إذا حدّد المشرف max_pages يدوياً
ALTER TABLE domains ADD COLUMN discovered_from BIGINT REFERENCES domains(id) ON DELETE SET NULL;
CREATE INDEX crawl_jobs_pending_domain_idx ON crawl_jobs (domain_id) WHERE status = 'pending';
CREATE INDEX domains_first_seen_idx ON domains (first_seen_at DESC);

INSERT INTO system_settings (key, value) VALUES
('crawler.discovery_mode',         '"iraq"'),   -- iraq: العراق + البذور فقط · open: الويب كله
('crawler.new_domain_budget',      '200'),      -- صفحات أولية لموقع غير عراقي مكتشف تلقائياً
('crawler.iraqi_domain_budget',    '10000'),
('crawler.max_budget',             '100000'),   -- سقف الميزانية التي تكبر مع سلطة الموقع
('crawler.max_pending_per_domain', '500'),      -- حتى لا يحتكر موقع واحد الطابور
('crawler.max_url_length',         '500')
ON CONFLICT (key) DO NOTHING;
