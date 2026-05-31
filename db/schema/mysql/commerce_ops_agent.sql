-- commerce_ops 인증/로깅 테이블 (Gateway/Agent용, MySQL). ERD.md §3 기반.
USE commerce_ops;

CREATE TABLE IF NOT EXISTS api_keys (
  id         CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  key_hash   VARCHAR(64) UNIQUE NOT NULL,        -- SHA-256 hex (평문 저장 금지)
  name       VARCHAR(128),
  team       VARCHAR(32),                         -- md / cs / ops / internal
  is_active  TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS prompt_versions (
  id            CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  agent_type    VARCHAR(32) NOT NULL,
  version_tag   VARCHAR(32) NOT NULL,
  system_prompt TEXT, user_template TEXT,
  is_active     TINYINT(1) NOT NULL DEFAULT 0,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_pv (agent_type, version_tag)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS agent_requests (
  id         CHAR(36) PRIMARY KEY,
  api_key_id CHAR(36), endpoint VARCHAR(64), query_text TEXT,
  agent_type VARCHAR(32), session_id VARCHAR(64),
  cache_hit  TINYINT(1), latency_ms INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_req_created (created_at), INDEX idx_req_key (api_key_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS agent_executions (
  id            CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  request_id    CHAR(36), status VARCHAR(16), generated_sql TEXT,
  rows_returned INT, latency_ms INT, result_summary JSON,
  finished_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_exec_req (request_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS model_usage_logs (
  id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
  request_id         CHAR(36), provider VARCHAR(32), model VARCHAR(64),
  prompt_tokens      INT, completion_tokens INT, estimated_cost_usd DECIMAL(10,6),
  created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_usage_created (created_at)
) ENGINE=InnoDB;

-- 데모 시드 (평문 키는 README/.env 문서화). 멱등.
INSERT IGNORE INTO api_keys (key_hash, name, team) VALUES
  (SHA2('oy_demo_md_key', 256),  'demo MD key',  'md'),
  (SHA2('oy_demo_voc_key', 256), 'demo VOC key', 'cs'),
  (SHA2('oy_demo_ops_key', 256), 'demo OPS key', 'ops');
