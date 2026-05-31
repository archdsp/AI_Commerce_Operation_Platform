-- 두 데이터베이스 생성 (docs/ERD.md §1, DATA.md §2). 'postgres' DB에 접속해 실행.
-- CREATE DATABASE는 트랜잭션/DO 블록 불가 → \gexec 조건부 실행 사용.
SELECT 'CREATE DATABASE olist_raw'
 WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'olist_raw')\gexec
SELECT 'CREATE DATABASE commerce_ops'
 WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'commerce_ops')\gexec
