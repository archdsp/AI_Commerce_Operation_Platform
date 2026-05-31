-- =====================================================================
-- commerce_ops : 운영·분석·집계·시뮬레이션
-- 근거: docs/ERD.md §3
-- 쓰기 주체: Gateway, Agent Workers, Kafka Consumers, Airflow, Simulator
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

-- ── 인증 ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash    VARCHAR UNIQUE NOT NULL,        -- 평문 저장 금지(SHA-256 hex)
    name        VARCHAR,
    team        VARCHAR,                         -- md / cs / ops / internal
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 프롬프트 버전 관리 ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_versions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type    VARCHAR NOT NULL,              -- router / md / voc / insight / text2sql
    version_tag   VARCHAR NOT NULL,
    system_prompt TEXT,
    user_template TEXT,                           -- {query}, {schema} 플레이스홀더
    is_active     BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (agent_type, version_tag)
);
-- agent_type당 활성 1개만 허용
CREATE UNIQUE INDEX IF NOT EXISTS uq_prompt_active
    ON prompt_versions(agent_type) WHERE is_active;

-- ── 요청/실행 로깅 ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_requests (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id  UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    endpoint    VARCHAR,                          -- /v1/chat 등
    query_text  TEXT,
    agent_type  VARCHAR,                          -- md / voc / insight / auto
    session_id  VARCHAR,
    cache_hit   BOOLEAN,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_req_key_time ON agent_requests(api_key_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_req_session  ON agent_requests(session_id);
CREATE INDEX IF NOT EXISTS idx_req_created  ON agent_requests(created_at);

CREATE TABLE IF NOT EXISTS agent_executions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id        UUID REFERENCES agent_requests(id) ON DELETE CASCADE,
    prompt_version_id UUID REFERENCES prompt_versions(id),
    status            VARCHAR,                    -- success / failed / sql_rejected
    generated_sql     TEXT,
    rows_returned     INT,
    latency_ms        INT,
    result_summary    JSONB,
    finished_at       TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_exec_request ON agent_executions(request_id);
CREATE INDEX IF NOT EXISTS idx_exec_status  ON agent_executions(status, finished_at);

-- ── 모델 사용량/비용 (RunPod: gpu_seconds 기반 비용 환산) ───────────
CREATE TABLE IF NOT EXISTS model_usage_logs (
    id                 BIGSERIAL PRIMARY KEY,
    request_id         UUID REFERENCES agent_requests(id) ON DELETE SET NULL,
    provider           VARCHAR,                   -- runpod / openai / anthropic
    model              VARCHAR,
    prompt_tokens      INT,
    completion_tokens  INT,
    estimated_cost_usd NUMERIC(10,6),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_usage_created ON model_usage_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_usage_model   ON model_usage_logs(provider, model, created_at);

-- ── 리뷰 분석 결과 (Kafka Review Analyzer 출력) ────────────────────
CREATE TABLE IF NOT EXISTS review_analysis (
    review_id       VARCHAR PRIMARY KEY,
    order_id        VARCHAR,
    product_id      VARCHAR,
    review_score    INT,
    sentiment       VARCHAR,                      -- positive / neutral / negative
    voc_category    VARCHAR,                      -- quality / delivery / price / service / other
    confidence      NUMERIC(4,3),
    analyzed_at     TIMESTAMPTZ DEFAULT now(),
    sim_review_date DATE                          -- 시뮬레이션 달력 (docs/DATA.md §4)
);
CREATE INDEX IF NOT EXISTS idx_ra_product_date ON review_analysis(product_id, sim_review_date);
CREATE INDEX IF NOT EXISTS idx_ra_voc          ON review_analysis(voc_category, sentiment);
CREATE INDEX IF NOT EXISTS idx_ra_date         ON review_analysis(sim_review_date);

-- ── 일별 카테고리 집계 (Airflow load_daily_metrics, Agent 사전집계 소스) ─
CREATE TABLE IF NOT EXISTS daily_category_metrics (
    metric_date           DATE,
    category_name_en      VARCHAR,
    gmv                   NUMERIC,
    order_count           INT,
    units_sold            INT,
    avg_review_score      NUMERIC,
    negative_review_count INT,
    voc_quality_count     INT,
    voc_delivery_count    INT,
    loaded_at             TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (metric_date, category_name_en)
);
CREATE INDEX IF NOT EXISTS idx_dcm_date ON daily_category_metrics(metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_dcm_cat  ON daily_category_metrics(category_name_en, metric_date);
