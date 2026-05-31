-- olist_raw (RDS MySQL / InnoDB / utf8mb4) — Postgres 스키마의 MySQL 포팅.
-- FK는 대량 적재 단순화를 위해 생략(인덱스만 유지). 적재 순서로 무결성 보장.
CREATE DATABASE IF NOT EXISTS olist_raw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE olist_raw;

CREATE TABLE IF NOT EXISTS category_translation (
  product_category_name          VARCHAR(128) PRIMARY KEY,
  product_category_name_english  VARCHAR(128)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS customers (
  customer_id               VARCHAR(64) PRIMARY KEY,
  customer_unique_id        VARCHAR(64),
  customer_zip_code_prefix  VARCHAR(16),
  customer_city             VARCHAR(128),
  customer_state            VARCHAR(8)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sellers (
  seller_id                 VARCHAR(64) PRIMARY KEY,
  seller_zip_code_prefix    VARCHAR(16),
  seller_city               VARCHAR(128),
  seller_state              VARCHAR(8)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS products (
  product_id                  VARCHAR(64) PRIMARY KEY,
  product_category_name       VARCHAR(128),
  product_name_lenght         INT,
  product_description_lenght  INT,
  product_photos_qty          INT,
  product_weight_g            INT,
  product_length_cm           INT,
  product_height_cm           INT,
  product_width_cm            INT,
  INDEX idx_products_category (product_category_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
  order_id                       VARCHAR(64) PRIMARY KEY,
  customer_id                    VARCHAR(64),
  order_status                   VARCHAR(32),
  order_purchase_timestamp       DATETIME NULL,
  order_approved_at              DATETIME NULL,
  order_delivered_carrier_date   DATETIME NULL,
  order_delivered_customer_date  DATETIME NULL,
  order_estimated_delivery_date  DATETIME NULL,
  INDEX idx_orders_customer (customer_id),
  INDEX idx_orders_purchase (order_purchase_timestamp)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_items (
  order_id             VARCHAR(64),
  order_item_id        INT,
  product_id           VARCHAR(64),
  seller_id            VARCHAR(64),
  shipping_limit_date  DATETIME NULL,
  price                DECIMAL(12,2),
  freight_value        DECIMAL(12,2),
  PRIMARY KEY (order_id, order_item_id),
  INDEX idx_oi_product (product_id),
  INDEX idx_oi_seller (seller_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS payments (
  order_id              VARCHAR(64),
  payment_sequential    INT,
  payment_type          VARCHAR(32),
  payment_installments  INT,
  payment_value         DECIMAL(12,2),
  PRIMARY KEY (order_id, payment_sequential)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS reviews (
  review_id               VARCHAR(64) PRIMARY KEY,
  order_id                VARCHAR(64),
  review_score            INT,
  review_comment_title    VARCHAR(255),
  review_comment_message  TEXT,
  review_creation_date    DATETIME NULL,
  review_answer_timestamp DATETIME NULL,
  INDEX idx_reviews_order (order_id),
  INDEX idx_reviews_score (review_score)
) ENGINE=InnoDB;
