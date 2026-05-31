-- commerce_ops (RDS MySQL) — #1(Metric Aggregator)에 필요한 테이블.
-- 나머지(api_keys, agent_requests, agent_executions, prompt_versions, model_usage_logs)는
-- Gateway/Agent 단계에서 추가한다.
CREATE DATABASE IF NOT EXISTS commerce_ops CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE commerce_ops;

-- Kafka Review Analyzer 출력 (멱등 UPSERT 대상)
CREATE TABLE IF NOT EXISTS review_analysis (
  review_id        VARCHAR(64) PRIMARY KEY,
  order_id         VARCHAR(64),
  product_id       VARCHAR(64),
  review_score     INT,
  sentiment        VARCHAR(16),     -- positive / neutral / negative
  voc_category     VARCHAR(16),     -- quality / delivery / price / service / other
  confidence       DECIMAL(4,3),
  analyzed_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  sim_review_date  DATE,
  INDEX idx_ra_date (sim_review_date),
  INDEX idx_ra_voc (voc_category, sentiment),
  INDEX idx_ra_order (order_id)
) ENGINE=InnoDB;

-- Metric Aggregator / Airflow 적재 대상 (Agent 사전집계 소스)
CREATE TABLE IF NOT EXISTS daily_category_metrics (
  metric_date            DATE,
  category_name_en       VARCHAR(128),
  gmv                    DECIMAL(16,2),
  order_count            INT,
  units_sold             INT,
  avg_review_score       DECIMAL(4,3),
  negative_review_count  INT,
  voc_quality_count      INT,
  voc_delivery_count     INT,
  loaded_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (metric_date, category_name_en),
  INDEX idx_dcm_date (metric_date)
) ENGINE=InnoDB;
