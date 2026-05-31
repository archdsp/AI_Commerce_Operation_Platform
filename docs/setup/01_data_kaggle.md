# 01. 데이터 — Kaggle Olist 준비

## 구성요소
Olist Brazilian E-Commerce 공개 데이터셋(CSV 9종). 시뮬레이터·DB·분석의 원천.

## 1) Kaggle API 토큰
1. kaggle.com → Account → **Create New API Token** → `kaggle.json` 다운로드
2. 배치:
```bash
mkdir -p ~/.kaggle && mv ~/Downloads/kaggle.json ~/.kaggle/
chmod 600 ~/.kaggle/kaggle.json
pip install kaggle
```

## 2) 다운로드 & 압축 해제
```bash
export OLIST_DATA_DIR=/home/ubuntu/Workspace/data       # 원하는 위치
mkdir -p "$OLIST_DATA_DIR"
kaggle datasets download -d olistbr/brazilian-ecommerce -p "$OLIST_DATA_DIR" --unzip
ls "$OLIST_DATA_DIR"/*.csv | wc -l      # 9 이어야 함
```

## 3) 사용하는 파일 (CSV 9종)
```
olist_customers_dataset.csv      olist_orders_dataset.csv
olist_order_items_dataset.csv    olist_order_payments_dataset.csv
olist_order_reviews_dataset.csv  olist_products_dataset.csv
olist_sellers_dataset.csv        olist_geolocation_dataset.csv
product_category_name_translation.csv
```

## 4) .env 등록
```bash
# .env
OLIST_DATA_DIR=/home/ubuntu/Workspace/data
```

> 다음: [02_python_env.md](./02_python_env.md)
