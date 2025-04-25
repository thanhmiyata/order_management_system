#!/bin/bash

# Script demo các tình huống lỗi
# Lưu ý: Đảm bảo đã chạy docker-compose, worker và API server trước khi chạy script này

echo "=== DEMO CÁC TÌNH HUỐNG LỖI ==="
echo "1. Lỗi validation đơn hàng"
echo "2. Lỗi thanh toán và retry"
echo "3. Lỗi tồn kho và rollback"
echo "============================="

# 1. Demo lỗi validation đơn hàng
echo -e "\n=== 1. DEMO LỖI VALIDATION ĐƠN HÀNG ==="
echo "Tạo đơn hàng với số lượng âm (sẽ gây lỗi validation)..."
ERROR_ORDER_RESPONSE=$(curl -s -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST123", "items": [{"product_id": "PROD-001", "quantity": -1, "price": 1299.99}], "total_amount": -1299.99}')

echo "Kết quả: $ERROR_ORDER_RESPONSE"

# 2. Demo lỗi thanh toán và retry
echo -e "\n=== 2. DEMO LỖI THANH TOÁN VÀ RETRY ==="
echo "Tạo đơn hàng hợp lệ..."
VALID_ORDER_RESPONSE=$(curl -s -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST123", "items": [{"product_id": "PROD-001", "quantity": 1, "price": 1299.99}], "total_amount": 1299.99}')

VALID_ORDER_ID=$(echo $VALID_ORDER_RESPONSE | jq -r '.order_id')
echo "Đơn hàng hợp lệ được tạo với ID: $VALID_ORDER_ID"

echo -e "\nPhê duyệt đơn hàng..."
curl -s -X POST "http://localhost:8000/orders/$VALID_ORDER_ID/approve"

echo -e "\nTạo thanh toán với số tiền không khớp (sẽ gây lỗi)..."
ERROR_PAYMENT_RESPONSE=$(curl -s -X POST "http://localhost:8000/payments" \
  -H "Content-Type: application/json" \
  -d "{\"order_id\": \"$VALID_ORDER_ID\", \"amount\": 999.99, \"method\": \"CREDIT_CARD\"}")

ERROR_PAYMENT_ID=$(echo $ERROR_PAYMENT_RESPONSE | jq -r '.payment_id')
echo "Thanh toán được tạo với ID: $ERROR_PAYMENT_ID"

echo -e "\nTheo dõi quá trình retry thanh toán..."
for i in {1..5}; do
  echo "Lần thử $i:"
  curl -s "http://localhost:8000/payments/$ERROR_PAYMENT_ID/status"
  sleep 2
done

# 3. Demo lỗi tồn kho và rollback
echo -e "\n=== 3. DEMO LỖI TỒN KHO VÀ ROLLBACK ==="
echo "Tạo đơn hàng với số lượng lớn hơn tồn kho..."
LARGE_ORDER_RESPONSE=$(curl -s -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST123", "items": [{"product_id": "PROD-001", "quantity": 1000, "price": 1299.99}], "total_amount": 1299990.00}')

LARGE_ORDER_ID=$(echo $LARGE_ORDER_RESPONSE | jq -r '.order_id')
echo "Đơn hàng số lượng lớn được tạo với ID: $LARGE_ORDER_ID"

echo -e "\nPhê duyệt đơn hàng..."
curl -s -X POST "http://localhost:8000/orders/$LARGE_ORDER_ID/approve"

echo -e "\nThử đặt trước hàng tồn kho (sẽ gây lỗi)..."
RESERVATION_RESPONSE=$(curl -s -X POST "http://localhost:8000/inventory/reserve" \
  -H "Content-Type: application/json" \
  -d "{\"order_id\": \"$LARGE_ORDER_ID\", \"items\": [{\"product_id\": \"PROD-001\", \"quantity\": 1000}]}")

RESERVATION_ID=$(echo $RESERVATION_RESPONSE | jq -r '.reservation_id')
echo "Đặt trước được tạo với ID: $RESERVATION_ID"

echo -e "\nTheo dõi quá trình rollback..."
for i in {1..3}; do
  echo "Trạng thái lần $i:"
  curl -s "http://localhost:8000/inventory/$RESERVATION_ID/status"
  sleep 2
done

echo -e "\n=== KẾT THÚC DEMO LỖI ===" 