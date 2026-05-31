"""edge_simulator 테스트용 소형 Olist CSV 픽스처."""
import pytest

SELLERS = """seller_id,seller_zip_code_prefix,seller_city,seller_state
sellerA,01001,sao paulo,SP
sellerB,13000,campinas,SP
"""

ORDERS = """order_id,customer_id,order_status,order_purchase_timestamp,order_approved_at,order_delivered_carrier_date,order_delivered_customer_date,order_estimated_delivery_date
order1,cust1,delivered,2018-01-10 10:00:00,2018-01-10 11:00:00,,,
order2,cust2,delivered,2018-02-15 09:30:00,2018-02-15 10:00:00,,,
"""

ITEMS = """order_id,order_item_id,product_id,seller_id,shipping_limit_date,price,freight_value
order1,1,prodX,sellerA,2018-01-15 10:00:00,100.00,10.00
order1,2,prodY,sellerA,2018-01-15 10:00:00,50.00,5.00
order2,1,prodZ,sellerB,2018-02-20 09:00:00,200.00,20.00
"""

# rev1 중복 행 포함 → dedup 검증
REVIEWS = """review_id,order_id,review_score,review_comment_title,review_comment_message,review_creation_date,review_answer_timestamp
rev1,order1,5,Bom,Gostei do produto,2018-01-20 00:00:00,2018-01-21 00:00:00
rev1,order1,5,Bom,Gostei do produto,2018-01-20 00:00:00,2018-01-21 00:00:00
rev2,order2,2,Ruim,Chegou com atraso,2018-02-25 00:00:00,2018-02-26 00:00:00
"""


@pytest.fixture
def olist_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    (d / "olist_sellers_dataset.csv").write_text(SELLERS, encoding="utf-8")
    (d / "olist_orders_dataset.csv").write_text(ORDERS, encoding="utf-8")
    (d / "olist_order_items_dataset.csv").write_text(ITEMS, encoding="utf-8")
    (d / "olist_order_reviews_dataset.csv").write_text(REVIEWS, encoding="utf-8")
    return d
