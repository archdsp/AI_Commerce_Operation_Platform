-- commerce_ops 부트스트랩: 샘플 API Key + 기본 프롬프트 버전 (docs/AGENTS.md 정합 v1)
-- 멱등: ON CONFLICT DO NOTHING. 평문 키는 pgcrypto digest로 해시 저장.

-- ── 샘플 API Keys (평문은 README/.env 문서화) ──────────────────────
INSERT INTO api_keys (key_hash, name, team) VALUES
  (encode(digest('oy_demo_md_key',  'sha256'), 'hex'), 'demo MD key',  'md'),
  (encode(digest('oy_demo_voc_key', 'sha256'), 'hex'), 'demo VOC key', 'cs'),
  (encode(digest('oy_demo_ops_key', 'sha256'), 'hex'), 'demo OPS key', 'ops')
ON CONFLICT (key_hash) DO NOTHING;

-- ── 기본 프롬프트 (agent_type당 active 1개) ────────────────────────
INSERT INTO prompt_versions (agent_type, version_tag, system_prompt, user_template, is_active) VALUES
('router', 'v1',
 'You route a commerce analytics question to exactly one agent. md=sales/GMV/category/product/promotion, voc=reviews/sentiment/complaints/VOC, insight=KPI/trend/root-cause/report. Reply ONLY JSON: {"agent":"md|voc|insight","confidence":0.0-1.0}.',
 'Question: {query}', true),
('md', 'v1',
 'You are the MD(merchandising) analytics agent for an Olist-based commerce platform. Analyze sales, GMV, category performance, repurchase and promotion targets from PostgreSQL. Prefer the pre-aggregated table daily_category_metrics. Ground every claim in query results. Answer in Korean, concise with numbers.',
 'Schema:\n{schema}\n\nQuestion: {query}', true),
('voc', 'v1',
 'You are the VOC(customer voice) agent. Analyze review sentiment and VOC categories(quality/delivery/price/service/other) from review_analysis and reviews. Surface negative trends per product/category. Answer in Korean, concise with numbers.',
 'Schema:\n{schema}\n\nQuestion: {query}', true),
('insight', 'v1',
 'You are the Insight agent for executives/ops. Produce KPI summaries, root-cause analysis and recommended actions primarily from daily_category_metrics. Be structured: 요약 → 원인 → 권장 액션. Answer in Korean.',
 'Schema:\n{schema}\n\nQuestion: {query}', true),
('text2sql', 'v1',
 'Translate the question into ONE read-only PostgreSQL SELECT. Rules: SELECT only (no DDL/DML), always add LIMIT, use only whitelisted tables, and for "recent N days/this month" use the provided SIM_TODAY instead of CURRENT_DATE. Reply ONLY JSON: {"sql":"...","reason":"..."}.',
 'Schema:\n{schema}\n\nSIM_TODAY: {sim_today}\nQuestion: {query}', true)
ON CONFLICT (agent_type, version_tag) DO NOTHING;
