# 04. 메시징 — AWS MSK Serverless

## 구성요소
Kafka 토픽 4종. 시뮬레이터가 발행 → 컨슈머(예정)가 소비.
| 토픽 | 파티션 | 용도 |
|------|--------|------|
| `order_events` | 6 | 점포 주문(매출) 이벤트 |
| `review_created` | 3 | 신규/시뮬 리뷰 |
| `review_analyzed` | 3 | 감성·VOC 분석 결과(컨슈머 출력) |
| `metric_updated` | 3 | 집계 갱신 알림 |
RF=3 (MSK Serverless 필수).

## 1) 클러스터 생성 (Serverless + IAM 인증)
```bash
aws kafka create-cluster-v2 --cluster-name cj-cluster-edge --region ap-northeast-2 \
  --serverless '{
    "vpcConfigs":[{"subnetIds":["subnet-a","subnet-b","subnet-c"],
                   "securityGroupIds":["sg-xxxx"]}],
    "clientAuthentication":{"sasl":{"iam":{"enabled":true}}}}'

aws kafka list-clusters-v2 --region ap-northeast-2          # State=ACTIVE 대기
```

## 2) 부트스트랩 주소 → .env
```bash
aws kafka get-bootstrap-brokers --cluster-arn <CLUSTER_ARN> --region ap-northeast-2 \
  --query BootstrapBrokerStringSaslIam --output text       # ...:9098
```
```bash
# .env
KAFKA_BOOTSTRAP_SERVERS=boot-xxxx.kafka-serverless.ap-northeast-2.amazonaws.com:9098
KAFKA_SECURITY_PROTOCOL=SASL_SSL
AWS_REGION=ap-northeast-2
```

## 3) 네트워크 (가장 흔한 함정)
- MSK Serverless 엔드포인트는 **VPC 사설 IP** → **같은 VPC + 보안그룹 9098 허용된 호스트**(예: 같은 VPC의 EC2)에서만 접속. 노트북에서 직접 X.
- SG 인바운드: `TCP 9098` from 프로듀서 SG/CIDR.

## 4) IAM 권한 (프로듀서/관리 주체 역할)
```json
{ "Effect":"Allow",
  "Action":["kafka-cluster:Connect","kafka-cluster:DescribeCluster",
            "kafka-cluster:*Topic*","kafka-cluster:WriteData","kafka-cluster:ReadData",
            "kafka-cluster:AlterGroup","kafka-cluster:DescribeGroup"],
  "Resource":["arn:aws:kafka:ap-northeast-2:<ACCT>:cluster/cj-cluster-edge/*",
              "arn:aws:kafka:ap-northeast-2:<ACCT>:topic/cj-cluster-edge/*",
              "arn:aws:kafka:ap-northeast-2:<ACCT>:group/cj-cluster-edge/*"] }
```
> 데모는 인스턴스 역할/자격증명으로 충분. 운영은 최소권한 역할 사용(root 키 금지).

## 5) 토픽 생성 / 목록 / 리셋
```bash
python scripts/kafka_admin.py --create     # 없는 토픽만 생성
python scripts/kafka_admin.py --list
python scripts/kafka_admin.py --reset      # 삭제+재생성 (개발/데모 전용)
```

## 비용
파티션-시간 + 처리량 과금 → 실험 후 `--reset` 또는 클러스터 정리.

> 다음: [05_edge_simulator.md](./05_edge_simulator.md)
