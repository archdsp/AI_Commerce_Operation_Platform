-- =====================================================================
-- olist_raw : Olist Brazilian E-Commerce 원본 스냅샷 (불변에 가까움)
-- 근거: docs/ERD.md §2, docs/DATA.md §1~2
-- 적재 순서(FK): category_translation → customers → sellers → products
--                → orders → order_items → payments → reviews
-- 주: zip_code_prefix는 선행 0 보존 위해 VARCHAR. 타임스탬프는 TIMESTAMP(naive).
-- =====================================================================

CREATE TABLE IF NOT EXISTS category_translation (
    product_category_name          VARCHAR PRIMARY KEY,
    product_category_name_english  VARCHAR
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id               VARCHAR PRIMARY KEY,
    customer_unique_id        VARCHAR,
    customer_zip_code_prefix  VARCHAR,
    customer_city             VARCHAR,
    customer_state            VARCHAR
);

CREATE TABLE IF NOT EXISTS sellers (
    seller_id                 VARCHAR PRIMARY KEY,
    seller_zip_code_prefix    VARCHAR,
    seller_city               VARCHAR,
    seller_state              VARCHAR
);

-- product_category_name은 일부 NULL/미번역 존재 → FK 강제하지 않음(소프트 참조)
CREATE TABLE IF NOT EXISTS products (
    product_id                  VARCHAR PRIMARY KEY,
    product_category_name       VARCHAR,
    product_name_lenght         NUMERIC,   -- 원본 CSV 철자 'lenght' 그대로 유지
    product_description_lenght  NUMERIC,
    product_photos_qty          NUMERIC,
    product_weight_g            NUMERIC,
    product_length_cm           NUMERIC,
    product_height_cm           NUMERIC,
    product_width_cm            NUMERIC
);

CREATE TABLE IF NOT EXISTS orders (
    order_id                       VARCHAR PRIMARY KEY,
    customer_id                    VARCHAR REFERENCES customers(customer_id),
    order_status                   VARCHAR,
    order_purchase_timestamp       TIMESTAMP,
    order_approved_at              TIMESTAMP,
    order_delivered_carrier_date   TIMESTAMP,
    order_delivered_customer_date  TIMESTAMP,
    order_estimated_delivery_date  TIMESTAMP
);

-- Olist 관례: 복합 PK (order_id, order_item_id)
CREATE TABLE IF NOT EXISTS order_items (
    order_id             VARCHAR REFERENCES orders(order_id),
    order_item_id        INT,
    product_id           VARCHAR REFERENCES products(product_id),
    seller_id            VARCHAR REFERENCES sellers(seller_id),
    shipping_limit_date  TIMESTAMP,
    price                NUMERIC,
    freight_value        NUMERIC,
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS payments (
    order_id              VARCHAR REFERENCES orders(order_id),
    payment_sequential    INT,
    payment_type          VARCHAR,
    payment_installments  INT,
    payment_value         NUMERIC,
    PRIMARY KEY (order_id, payment_sequential)
);

-- review_id는 Olist 원본에 중복 행이 존재 → 적재 시 dedupe(시드 스크립트 참조).
-- order_id FK는 강제하지 않음(일부 매칭 이슈 회피).
CREATE TABLE IF NOT EXISTS reviews (
    review_id               VARCHAR PRIMARY KEY,
    order_id                VARCHAR,
    review_score            INT,
    review_comment_title    VARCHAR,
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMP,
    review_answer_timestamp TIMESTAMP
);

-- 인덱스 (docs/ERD.md §2.3)
CREATE INDEX IF NOT EXISTS idx_orders_customer     ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_purchase_ts  ON orders(order_purchase_timestamp);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_seller  ON order_items(seller_id);
CREATE INDEX IF NOT EXISTS idx_reviews_order       ON reviews(order_id);
CREATE INDEX IF NOT EXISTS idx_reviews_creation    ON reviews(review_creation_date);
CREATE INDEX IF NOT EXISTS idx_reviews_score       ON reviews(review_score);
CREATE INDEX IF NOT EXISTS idx_payments_order      ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_products_category   ON products(product_category_name);
