-- سومر: المخطط الأساسي
-- مبدأ: لا يوجد أي جدول يحفظ استعلامات المستخدمين أو عناوين IP لزوار البحث.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============ اللغات ============
CREATE TABLE language_metadata (
    code        TEXT PRIMARY KEY,                 -- ar, ckb, en ...
    name        TEXT NOT NULL,
    native_name TEXT NOT NULL,
    direction   TEXT NOT NULL CHECK (direction IN ('rtl', 'ltr')),
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    priority    REAL NOT NULL DEFAULT 1.0,         -- وزن اللغة في الترتيب
    analyzer    TEXT NOT NULL DEFAULT 'simple'
);
INSERT INTO language_metadata (code, name, native_name, direction, priority, analyzer) VALUES
    ('ar',  'Arabic',          'العربية',  'rtl', 1.0, 'arabic'),
    ('ckb', 'Kurdish (Sorani)', 'کوردی',   'rtl', 1.0, 'kurdish'),
    ('kmr', 'Kurdish (Kurmanji)', 'Kurmancî', 'ltr', 0.9, 'latin'),
    ('en',  'English',         'English',  'ltr', 0.9, 'english');

-- ============ النطاقات ============
CREATE TABLE domains (
    id                  BIGSERIAL PRIMARY KEY,
    host                TEXT NOT NULL UNIQUE,
    is_iraqi            BOOLEAN NOT NULL DEFAULT FALSE,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'paused', 'blocked')),
    block_reason        TEXT,
    category            TEXT,                       -- gov, edu, news, business ...
    reputation          REAL NOT NULL DEFAULT 0.5,  -- 0..1
    authority           REAL NOT NULL DEFAULT 0.0,  -- PageRank على مستوى النطاق
    crawl_depth         INT  NOT NULL DEFAULT 3 CHECK (crawl_depth BETWEEN 0 AND 20),
    crawl_frequency_h   INT  NOT NULL DEFAULT 168 CHECK (crawl_frequency_h >= 1),
    min_delay_ms        INT  NOT NULL DEFAULT 1000 CHECK (min_delay_ms >= 100),
    max_pages           INT  NOT NULL DEFAULT 10000,
    render_js           BOOLEAN NOT NULL DEFAULT FALSE,
    excluded_paths      TEXT[] NOT NULL DEFAULT '{}',
    robots_txt          TEXT,
    robots_crawl_delay  REAL,
    robots_fetched_at   TIMESTAMPTZ,
    page_count          INT NOT NULL DEFAULT 0,
    error_count         INT NOT NULL DEFAULT 0,
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_crawled_at     TIMESTAMPTZ
);
CREATE INDEX domains_status_idx ON domains (status);
CREATE INDEX domains_iraqi_idx ON domains (is_iraqi) WHERE is_iraqi;

CREATE TABLE seed_urls (
    id         BIGSERIAL PRIMARY KEY,
    url        TEXT NOT NULL UNIQUE,
    domain_id  BIGINT REFERENCES domains(id) ON DELETE CASCADE,
    added_by   BIGINT,
    added_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ الصفحات المزحوفة ============
CREATE TABLE crawled_pages (
    id              BIGSERIAL PRIMARY KEY,
    url             TEXT NOT NULL,
    url_hash        BYTEA NOT NULL UNIQUE,          -- sha256(url) يُحسب بالتطبيق
    domain_id       BIGINT NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    canonical_url   TEXT,
    depth           INT NOT NULL DEFAULT 0,
    http_status     INT,
    content_type    TEXT,
    content_hash    BYTEA,
    simhash         BIGINT,
    etag            TEXT,
    last_modified   TEXT,
    redirected_to   TEXT,
    status          TEXT NOT NULL DEFAULT 'ok'
                    CHECK (status IN ('ok', 'not_modified', 'redirect', 'broken', 'error', 'robots_blocked', 'excluded', 'noindex', 'duplicate', 'too_large', 'unsupported')),
    error           TEXT,
    crawl_count     INT NOT NULL DEFAULT 0,
    first_crawled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_crawled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_crawl_at   TIMESTAMPTZ
);
CREATE INDEX crawled_pages_domain_idx ON crawled_pages (domain_id);
CREATE INDEX crawled_pages_next_idx ON crawled_pages (next_crawl_at) WHERE status IN ('ok', 'not_modified');
CREATE INDEX crawled_pages_content_hash_idx ON crawled_pages (content_hash);
CREATE INDEX crawled_pages_status_idx ON crawled_pages (status);

-- ============ إصدارات الفهرس ============
CREATE TABLE index_versions (
    id               SERIAL PRIMARY KEY,
    label            TEXT NOT NULL,
    analyzer_version INT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'building' CHECK (status IN ('building', 'active', 'retired', 'failed')),
    doc_count        BIGINT NOT NULL DEFAULT 0,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX index_versions_one_active ON index_versions ((status)) WHERE status = 'active';

-- ============ المستندات المفهرسة ============
CREATE TABLE indexed_documents (
    page_id          BIGINT PRIMARY KEY REFERENCES crawled_pages(id) ON DELETE CASCADE,
    domain_id        BIGINT NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    url              TEXT NOT NULL,
    title            TEXT NOT NULL DEFAULT '',
    description      TEXT NOT NULL DEFAULT '',
    headings         TEXT NOT NULL DEFAULT '',
    body             TEXT NOT NULL DEFAULT '',
    lang             TEXT REFERENCES language_metadata(code),
    category         TEXT NOT NULL DEFAULT 'web',
    doc_type         TEXT NOT NULL DEFAULT 'html' CHECK (doc_type IN ('html', 'pdf')),
    tsv              TSVECTOR NOT NULL,
    title_norm       TEXT NOT NULL DEFAULT '',
    word_count       INT NOT NULL DEFAULT 0,
    quality          REAL NOT NULL DEFAULT 0.5,
    spam_score       REAL NOT NULL DEFAULT 0.0,
    is_adult         BOOLEAN NOT NULL DEFAULT FALSE,
    published_at     TIMESTAMPTZ,
    duplicate_of     BIGINT REFERENCES crawled_pages(id) ON DELETE SET NULL,
    analyzer_version INT NOT NULL,
    index_version_id INT REFERENCES index_versions(id),
    indexed_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX indexed_documents_tsv_idx ON indexed_documents USING GIN (tsv);
CREATE INDEX indexed_documents_title_trgm ON indexed_documents USING GIN (title_norm gin_trgm_ops);
CREATE INDEX indexed_documents_domain_idx ON indexed_documents (domain_id);
CREATE INDEX indexed_documents_cat_idx ON indexed_documents (category);
CREATE INDEX indexed_documents_lang_idx ON indexed_documents (lang);
CREATE INDEX indexed_documents_indexed_at_idx ON indexed_documents (indexed_at DESC);
CREATE INDEX indexed_documents_dup_idx ON indexed_documents (duplicate_of) WHERE duplicate_of IS NOT NULL;

CREATE TABLE document_metadata (
    page_id       BIGINT PRIMARY KEY REFERENCES crawled_pages(id) ON DELETE CASCADE,
    meta          JSONB NOT NULL DEFAULT '{}',
    hreflang      JSONB NOT NULL DEFAULT '{}',
    author        TEXT,
    site_name     TEXT,
    og_type       TEXT
);

-- قاموس المصطلحات المفهرسة (لتصحيح الإملاء والإكمال التلقائي) — من المحتوى، لا من المستخدمين
CREATE TABLE index_terms (
    term TEXT PRIMARY KEY,
    df   INT NOT NULL
);
CREATE INDEX index_terms_trgm ON index_terms USING GIN (term gin_trgm_ops);

-- ============ الروابط ============
CREATE TABLE page_links (
    src_page_id   BIGINT NOT NULL REFERENCES crawled_pages(id) ON DELETE CASCADE,
    dst_url_hash  BYTEA NOT NULL,
    dst_url       TEXT NOT NULL,
    dst_domain_id BIGINT REFERENCES domains(id) ON DELETE CASCADE,
    anchor        TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (src_page_id, dst_url_hash)
);
CREATE INDEX page_links_dst_idx ON page_links (dst_url_hash);
CREATE INDEX page_links_dst_domain_idx ON page_links (dst_domain_id);

-- ============ مهام الزحف والفهرسة ============
CREATE TABLE crawl_jobs (
    id            BIGSERIAL PRIMARY KEY,
    kind          TEXT NOT NULL CHECK (kind IN ('crawl', 'sitemap', 'image', 'reindex_domain', 'rebuild_index', 'delete_outdated', 'compute_authority', 'refresh_terms', 'retention', 'backup')),
    url           TEXT,
    domain_id     BIGINT REFERENCES domains(id) ON DELETE CASCADE,
    page_id       BIGINT,
    depth         INT NOT NULL DEFAULT 0,
    priority      INT NOT NULL DEFAULT 100,           -- الأصغر أولاً
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'running', 'done', 'failed', 'cancelled')),
    attempts      INT NOT NULL DEFAULT 0,
    max_attempts  INT NOT NULL DEFAULT 3,
    payload       JSONB NOT NULL DEFAULT '{}',
    error         TEXT,
    worker        TEXT,
    created_by    BIGINT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    scheduled_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ
);
CREATE INDEX crawl_jobs_claim_idx ON crawl_jobs (priority, scheduled_at) WHERE status = 'pending';
CREATE INDEX crawl_jobs_status_idx ON crawl_jobs (status, kind);
CREATE UNIQUE INDEX crawl_jobs_pending_url ON crawl_jobs (kind, md5(url)) WHERE status IN ('pending', 'running') AND url IS NOT NULL;

CREATE TABLE crawl_logs (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    level       TEXT NOT NULL CHECK (level IN ('info', 'warn', 'error')),
    event       TEXT NOT NULL,          -- fetched, robots_blocked, ssrf_blocked, http_error, redirect, ...
    url         TEXT,
    domain_id   BIGINT REFERENCES domains(id) ON DELETE CASCADE,
    http_status INT,
    duration_ms INT,
    message     TEXT
);
CREATE INDEX crawl_logs_ts_idx ON crawl_logs (ts DESC);
CREATE INDEX crawl_logs_event_idx ON crawl_logs (event, ts DESC);

-- ============ الصور ============
CREATE TABLE image_index (
    id            BIGSERIAL PRIMARY KEY,
    image_url     TEXT NOT NULL,
    url_hash      BYTEA NOT NULL UNIQUE,
    page_id       BIGINT REFERENCES crawled_pages(id) ON DELETE CASCADE,
    domain_id     BIGINT REFERENCES domains(id) ON DELETE CASCADE,
    alt           TEXT NOT NULL DEFAULT '',
    context       TEXT NOT NULL DEFAULT '',
    tsv           TSVECTOR,
    width         INT,
    height        INT,
    format        TEXT,
    bytes         INT,
    dhash         BIGINT,
    band0         INT, band1 INT, band2 INT, band3 INT,
    thumb_path    TEXT,
    embedding_ok  BOOLEAN NOT NULL DEFAULT FALSE,
    status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'ok', 'failed', 'duplicate', 'blocked')),
    error         TEXT,
    duplicate_of  BIGINT REFERENCES image_index(id) ON DELETE SET NULL,
    is_adult      BOOLEAN NOT NULL DEFAULT FALSE,
    fetched_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX image_index_tsv_idx ON image_index USING GIN (tsv);
CREATE INDEX image_index_status_idx ON image_index (status);
CREATE INDEX image_index_band0 ON image_index (band0);
CREATE INDEX image_index_band1 ON image_index (band1);
CREATE INDEX image_index_band2 ON image_index (band2);
CREATE INDEX image_index_band3 ON image_index (band3);

-- ============ إشارات السبام ============
CREATE TABLE spam_signals (
    id         BIGSERIAL PRIMARY KEY,
    page_id    BIGINT NOT NULL REFERENCES crawled_pages(id) ON DELETE CASCADE,
    signal     TEXT NOT NULL,
    score      REAL NOT NULL,
    details    TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (page_id, signal)
);

-- ============ المشرفون والصلاحيات ============
CREATE TABLE admin_roles (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    label_ar    TEXT NOT NULL,
    label_en    TEXT NOT NULL,
    permissions TEXT[] NOT NULL DEFAULT '{}',
    is_system   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE admin_users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    role_id         INT NOT NULL REFERENCES admin_roles(id),
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    totp_secret_enc TEXT,            -- مشفّر بمفتاح التطبيق
    totp_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    failed_logins   INT NOT NULL DEFAULT 0,
    locked_until    TIMESTAMPTZ,
    must_change_pw  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      BIGINT REFERENCES admin_users(id),
    last_login_at   TIMESTAMPTZ
);

CREATE TABLE admin_sessions (
    token_hash   BYTEA PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    csrf_token   TEXT NOT NULL,
    mfa_passed   BOOLEAN NOT NULL DEFAULT FALSE,
    ip           INET,               -- للمشرفين فقط، لأغراض أمنية
    user_agent   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    revoked_at   TIMESTAMPTZ
);
CREATE INDEX admin_sessions_user_idx ON admin_sessions (user_id);

CREATE TABLE audit_logs (
    id         BIGSERIAL PRIMARY KEY,
    ts         TIMESTAMPTZ NOT NULL DEFAULT now(),
    admin_id   BIGINT REFERENCES admin_users(id) ON DELETE SET NULL,
    admin_email TEXT,
    action     TEXT NOT NULL,
    target     TEXT,
    details    JSONB NOT NULL DEFAULT '{}',
    ip         INET,
    success    BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX audit_logs_ts_idx ON audit_logs (ts DESC);
CREATE INDEX audit_logs_admin_idx ON audit_logs (admin_id, ts DESC);

-- أحداث أمنية: منفصلة تماماً عن أي بيانات بحث، ولا تحتوي IP زوار البحث
CREATE TABLE security_events (
    id       BIGSERIAL PRIMARY KEY,
    ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind     TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    details  JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX security_events_ts_idx ON security_events (ts DESC);

-- ============ الإعدادات ============
CREATE TABLE system_settings (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by BIGINT REFERENCES admin_users(id) ON DELETE SET NULL
);

-- ============ تحليلات تشغيلية مجمّعة (بدون استعلامات أو هويات) ============
CREATE TABLE ops_metrics_hourly (
    hour   TIMESTAMPTZ NOT NULL,
    metric TEXT NOT NULL,       -- searches, errors, latency_ms_sum, lang:*, category:*
    dim    TEXT NOT NULL DEFAULT '',
    value  BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (hour, metric, dim)
);

CREATE TABLE backups (
    id          BIGSERIAL PRIMARY KEY,
    file_name   TEXT NOT NULL,
    bytes       BIGINT,
    sha256      TEXT,
    encrypted   BOOLEAN NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('running', 'ok', 'failed')),
    error       TEXT,
    created_by  BIGINT REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);
