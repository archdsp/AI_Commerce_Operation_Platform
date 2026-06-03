# 🖥️ 로컬 실행 가이드 (AWS 없이)

이 플랫폼을 **개인 PC에서 AWS 없이** 전 구간(데이터→스트리밍→집계→RAG→멀티에이전트→게이트웨이) 구동한다.
관리형 인프라를 로컬 대체로 갈아끼우되 **코드는 운영과 동일**하다 — 차이는 `.env.local` 설정뿐이다.

> 대상: **macOS(Apple Silicon)** · **Linux** · **Windows(WSL Ubuntu 24.04)**.
> Windows 네이티브 PowerShell은 [§Windows](#-windows-wsl-권장--powershell)를 참고.

---

## AWS → 로컬 매핑

| 역할 | 운영(AWS) | 로컬 |
|---|---|---|
| 관계형 DB | RDS MySQL 8.4 | **Docker `mysql:8.4`** |
| 이벤트 스트림 | MSK Serverless(IAM) | **Docker Redpanda**(Kafka 호환, PLAINTEXT) |
| 벡터 검색(RAG) | 셀프호스트 Qdrant | **Docker `qdrant/qdrant`** |
| LLM 추론 | RunPod vLLM(Qwen2.5-7B) | **Ollama `qwen2.5:7b`**(Metal/CUDA 가속) |
| 임베딩 | fastembed(로컬 ONNX) | 동일(로컬) |
| 배치 | MWAA(Airflow) | (로컬 데모 범위 외) |

코드 교체점은 단 셋이며 전부 **설정만**으로 동작한다: Kafka는 `KAFKA_*`, DB는 `MYSQL_*`,
LLM은 `VLLM_URL`(OpenAI 호환). `ENV_FILE=.env.local`이면 앱이 이 프로파일을 우선 로드한다.

---

## 사전 요건

| 도구 | 용도 | 설치 |
|---|---|---|
| **Docker** (Desktop/Engine) | MySQL·Redpanda·Qdrant 컨테이너 | macOS/Win: Docker Desktop · Linux: docker-ce + compose plugin |
| **Ollama** | 로컬 LLM(`qwen2.5:7b`) | https://ollama.com (macOS 앱 / `curl -fsSL https://ollama.com/install.sh \| sh`) |
| **Python 3.11+** | 앱(게이트웨이·컨슈머·시뮬레이터) | `pip install -r requirements.txt` (가상환경 권장) |

> 최초 1회 네트워크 다운로드: Docker 이미지(수백 MB), Ollama 모델 `qwen2.5:7b`(~4.7GB),
> fastembed 임베딩 모델(~120MB). 이후엔 오프라인 동작.

---

## 빠른 시작 (한 커맨드)

```bash
git clone <repo> && cd AI_Commerce_Operation_Platform
python -m venv .venv && source .venv/bin/activate     # (선택) 가상환경
pip install -r requirements.txt

cp .env.local.example .env.local      # 필요 시 값 조정
ollama serve &                        # macOS 앱 사용 시 생략 가능
scripts/local/up.sh                   # 인프라+파이프라인+게이트웨이 일괄 기동
```

`up.sh`가 끝나면:

```bash
open http://localhost:8000            # 웹 채팅 UI (Linux: xdg-open)

curl -s -X POST http://localhost:8000/v1/chat \
  -H 'Content-Type: application/json' -H 'X-API-Key: oy_demo_md_key' \
  -d '{"query":"판매량이 가장 많은 카테고리는?"}'
```

**데모 API 키**(평문): `oy_demo_md_key`(MD) · `oy_demo_voc_key`(VOC) · `oy_demo_ops_key`(OPS).

종료: `scripts/local/down.sh` (`--purge`로 볼륨까지 완전 초기화).

---

## up.sh가 하는 일 (수동 단계)

문제 추적 시 단계별 수동 실행 — 모두 `ENV_FILE=.env.local` 전제(`export ENV_FILE=.env.local`).

```bash
docker compose -f docker-compose.local.yml up -d        # 1) 인프라(MySQL·Redpanda·Qdrant)
ollama pull qwen2.5:7b                                   # 2) LLM 모델
python scripts/setup_mysql.py                            # 3) 스키마 3종 + olist_raw 샘플 적재 + api_keys 시드
python scripts/prepare_edges.py                          # 4) 샘플 → 점포별 엣지 샤드
python scripts/kafka_admin.py --create                   # 5) Redpanda 토픽 생성
python scripts/run.py --rate 4000 --duration 120         # 6) 발행(시뮬레이터)
python scripts/review_analyzer.py  --duration 30         #    감성/VOC(휴리스틱) → review_analysis
python scripts/metric_aggregator.py --duration 30        #    카테고리×일자 집계 → daily_category_metrics
python scripts/reload_qdrant.py --limit 6000             # 7) 리뷰 임베딩 → Qdrant(RAG)
scripts/local/serve.sh start                             # 8) 게이트웨이 :8000
```

> 검증 포인트: `/health` → `/v1/chat` 라우팅+Text-to-SQL(Ollama)+한국어 답변 → 웹 UI →
> `daily_category_metrics` 채워짐 → VOC 질의 시 RAG 검색 동작.
> 회귀 테스트: `pytest tests` (인프라 불요 단위 테스트).

---

## GPU 가속

| 플랫폼 | GPU | 비고 |
|---|---|---|
| macOS Apple Silicon | Metal | Ollama 자동 사용. 16GB+면 `qwen2.5:7b` 쾌적 |
| Linux/Windows + NVIDIA | CUDA | Ollama 자동 감지. **RTX 4070 Ti**면 7b 여유, `qwen2.5:14b`도 가능 |
| WSL2 + NVIDIA | CUDA-on-WSL | Windows 호스트 드라이버만 있으면 WSL `nvidia-smi` 동작 → Ollama가 GPU 사용 |

확인: `ollama ps`(모델이 GPU에 로드됐는지) · NVIDIA는 `nvidia-smi`. CPU만 있어도 동작하나 7b는 느리므로
`VLLM_MODEL=qwen2.5:3b` 또는 `1.5b`로 낮춘다(`.env.local`).

---

## 🪟 Windows (WSL 권장 · /  PowerShell)

**권장: WSL Ubuntu 24.04** — 위 bash 절차가 그대로 동작한다.

1. **WSL + Ubuntu 24.04**: PowerShell(관리자)에서 `wsl --install -d Ubuntu-24.04`.
2. **Docker Desktop**: 설치 후 *Settings → Resources → WSL Integration*에서 Ubuntu-24.04 토글 ON.
3. **NVIDIA GPU(RTX 4070 Ti)**: Windows에 최신 NVIDIA 드라이버만 설치하면 WSL2에서 CUDA 패스스루가 된다
   (WSL 안에 별도 드라이버 설치 금지). Ubuntu 셸에서 `nvidia-smi`로 확인.
4. **Ollama**: WSL Ubuntu 안에서 `curl -fsSL https://ollama.com/install.sh | sh` → `ollama serve &`
   (WSL의 Ollama가 GPU 사용). *또는* Windows용 Ollama를 쓰고 WSL에서 `VLLM_URL`을 Windows 호스트로 가리켜도 된다.
5. 이후 **빠른 시작**과 동일: `cp .env.local.example .env.local && scripts/local/up.sh`.

> i9 · 64GB · RTX 4070 Ti 환경이면 7b가 GPU에서 빠르게 돌고 Docker 3컨테이너도 여유롭다.

**네이티브 PowerShell** 경로(WSL 미사용)는 후속 추가 예정 — `scripts/local/*.ps1`.

---

## 전체 Olist 데이터로 교체 (선택)

기본은 레포에 커밋된 **소형 샘플**(`data/olist_sample/`, 5,000주문·68카테고리)로 자급 동작한다.
전체 데이터(주문 ~99k)로 더 풍부한 데모를 원하면 [Kaggle Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
9개 CSV를 받아 한 줄만 바꾼다:

```bash
# .env.local
OLIST_DATA_DIR=/abs/path/to/olist_full      # 9개 CSV가 있는 디렉터리
```

후 `scripts/local/up.sh` 재실행(멱등 재적재). 샘플 재생성: `python scripts/make_local_sample.py --src <full> --orders 5000`.

---

## 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| `up.sh`가 MySQL health에서 멈춤 | 포트 3306 충돌 → 기존 MySQL 종료 또는 compose 포트 변경. `docker logs acop-mysql` |
| `caching_sha2_password` / 인증 오류 | `pip install -r requirements.txt`(=`cryptography` 포함) 재확인 |
| Redpanda 연결 실패 | 9092 충돌 확인. `docker logs acop-redpanda`. WSL은 Docker Desktop WSL 통합 ON 확인 |
| `/v1/chat`가 500/타임아웃 | Ollama 미기동/모델 미수신 → `ollama serve` + `ollama list`에 `qwen2.5:7b` 확인 |
| 첫 RAG 질의가 느림 | fastembed 모델 최초 다운로드(~120MB) + 7b 로딩. 두 번째부터 빠름 |
| 답변이 빈약/환각 | 저용량 모델 사용 시 발생 → `qwen2.5:7b` 이상 권장 |
| 포트가 이미 사용 중 | 이 레포의 운영 데모(serve_demo.sh)나 다른 Qdrant가 떠 있는지 확인 |

---

## 운영(AWS) 모드와의 관계

- 운영 경로는 그대로다. `ENV_FILE` 미설정 시 앱은 기존 `.env`(AWS/RunPod)를 사용한다.
- 로컬은 `ENV_FILE=.env.local`(로컬 스크립트가 자동 설정)일 때만 활성화 — **비파괴·가산적**.
- 전체 아키텍처/운영: [README](../README.md) · [ARCHITECTURE](./ARCHITECTURE.md) · [DEPLOYMENT](./DEPLOYMENT.md).
