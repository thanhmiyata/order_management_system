#!/bin/bash

# Script demo 3 quy trình chính: phê duyệt, thanh toán, quản lý kho hàng
# Lưu ý: Đảm bảo đã chạy docker-compose, worker và API server trước khi chạy script này

echo "=== DEMO 3 QUY TRÌNH CHÍNH ==="
echo "1. Quy trình phê duyệt đơn hàng"
echo "2. Quy trình thanh toán"
echo "3. Quy trình quản lý kho hàng"
echo "============================="

# 1. Demo quy trình phê duyệt đơn hàng
echo -e "\n=== 1. DEMO QUY TRÌNH PHÊ DUYỆT ĐƠN HÀNG ==="
echo "Tạo đơn hàng mới..."
ORDER_RESPONSE=$(curl -s -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST123", "items": [{"product_id": "PROD-001", "quantity": 2, "price": 1299.99}], "total_amount": 2599.98}')

ORDER_ID=$(echo $ORDER_RESPONSE | jq -r '.order_id')
echo "Đơn hàng được tạo với ID: $ORDER_ID"

# Chờ 5 giây để workflow khởi tạo và validate
sleep 5

echo -e "\nKiểm tra trạng thái đơn hàng..."
curl -s "http://localhost:8000/orders/$ORDER_ID/status"

echo -e "\nPhê duyệt đơn hàng..."
curl -s -X POST "http://localhost:8000/orders/$ORDER_ID/approve"

# Chờ 5 giây để workflow xử lý phê duyệt
sleep 5

echo -e "\nKiểm tra trạng thái sau khi phê duyệt..."
curl -s "http://localhost:8000/orders/$ORDER_ID/status"

# 2. Demo quy trình thanh toán
echo -e "\n=== 2. DEMO QUY TRÌNH THANH TOÁN ==="
echo "Tạo thanh toán mới..."
PAYMENT_RESPONSE=$(curl -s -X POST "http://localhost:8000/payments" \
  -H "Content-Type: application/json" \
  -d "{\"order_id\": \"$ORDER_ID\", \"amount\": 2599.98, \"payment_method\": \"CREDIT_CARD\"}")

PAYMENT_ID=$(echo $PAYMENT_RESPONSE | jq -r '.payment_id')
echo "Thanh toán được tạo với ID: $PAYMENT_ID"

echo -e "\nKiểm tra trạng thái thanh toán..."
curl -s "http://localhost:8000/payments/$PAYMENT_ID/status"

# 3. Demo quy trình quản lý kho hàng
echo -e "\n=== 3. DEMO QUY TRÌNH QUẢN LÝ KHO HÀNG ==="
echo "Kiểm tra tồn kho sản phẩm..."
curl -s "http://localhost:8000/inventory/PROD-001/check?quantity=2"

echo -e "\nĐặt trước hàng tồn kho..."
RESERVATION_RESPONSE=$(curl -s -X POST "http://localhost:8000/inventory/reserve" \
  -H "Content-Type: application/json" \
  -d "{\"order_id\": \"$ORDER_ID\", \"items\": [{\"product_id\": \"PROD-001\", \"quantity\": 2}]}")

RESERVATION_ID=$(echo $RESERVATION_RESPONSE | jq -r '.reservation_id')
echo "Đặt trước được tạo với ID: $RESERVATION_ID"

echo -e "\nXác nhận đặt trước..."
curl -s -X POST "http://localhost:8000/inventory/commit/$RESERVATION_ID"

echo -e "\n=== KẾT THÚC DEMO ===" 