-- Text-to-SQL 전용 읽기전용 로그인 롤 (Agent가 이 롤로 olist_raw/commerce_ops 조회).
-- 권한 격리: Agent SQL은 SELECT만 가능. 실제 GRANT는 스키마 적용 후 setup 스크립트가 수행.
-- 데모 비밀번호 — 운영 배포 시 Secrets Manager 값으로 교체할 것.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 't2s_readonly') THEN
    CREATE ROLE t2s_readonly LOGIN PASSWORD 'readonly_demo_pw';
  END IF;
END $$;
