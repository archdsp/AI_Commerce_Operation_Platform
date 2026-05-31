# 05. 엣지 점포 시뮬레이터

**전제:** 01(데이터) · 02(환경) · 04(MSK 토픽) 완료.

## 코드 구조 (src=모듈 / scripts=엔트리)
```text
src/edge_simulator/         # 구성요소(모듈)만
  config.py        env/Kafka 설정·경로
  logging_setup.py loguru → /workspace/app_logs/{app_name}
  kafka_auth.py    MSK IAM(OAUTHBEARER) 공통 인증
  prepare.py       CSV → 점포별 이벤트/샤드 (분할 로직)
  shards.py        샤드 로딩
  producer.py      샤드 → MSK 발행 (Pacer·합성복제·다중샤드)
  admin.py         토픽 생성/리셋/목록
  verify.py        도착 검증(소비)
scripts/                    # CLI 진입점 (얇음, src 호출)
  prepare_edges.py  run.py  kafka_admin.py  consume_check.py
```

## 1) 데이터 분할 → **분할 데이터 위치 = `data/edges/`**
```bash
python scripts/prepare_edges.py                      # 636 노드(state/city) → data/edges/*.jsonl + manifest.json
python scripts/prepare_edges.py --granularity seller # 셀러 3,095개 단위
```
- 노드당 1파일(JSONL), 한 줄 = 발행할 레코드 `{key, kind, ts, value:{봉투}}`
- `data/edges/manifest.json` = 노드 목록·이벤트수·기간 (gitignore됨, ~113MB)

## 2) 발행 (샤드 → MSK)
```bash
python scripts/run.py                                # 전체(TAF 가속)
python scripts/run.py --dry-run --max-events 20000   # 브로커 없이 점검
python scripts/run.py --rate 2000 --max-events 5000  # 소량 실발행
```

## 3) 도착 검증
```bash
python scripts/consume_check.py --sample 3
# → [consumed] {'order_events': N1, 'review_created': N2}
```

## 🔄 리셋 / ♻️ 재현
```bash
python scripts/kafka_admin.py --reset                # 토픽 비우기(오프셋 0)
# 재현: event_id=uuid5(결정론), occurred_at=SIM_TODAY 시프트 → 동일 입력=동일 발행
python scripts/prepare_edges.py --sim-today 2026-05-31
python scripts/run.py
```

## 📈 대용량 트래픽 실험
```bash
python scripts/run.py --scale 50 --rate 20000          # 점포 ×50, 2만 msg/s
python scripts/run.py --shard-count 3 --shard-index 0  # 0/1/2를 머신·컨테이너별 분산
python scripts/run.py --rate 50000 --loop              # 지속 부하
```
> 컨슈머 병렬성 상한 = 파티션 수. 더 큰 부하는 파티션↑. 실험 후 `--reset`(과금 주의).

## 로그 / 테스트
```bash
ls /workspace/app_logs/edge_simulator/      # loguru 파일 로그
pytest tests/edge_simulator -v              # 유닛테스트
```

## 검증 기록
실제 MSK Serverless `cj-cluster-edge`(ap-northeast-2)로 **5,438건 발행(err 0) → 5,459건 소비** 확인.
