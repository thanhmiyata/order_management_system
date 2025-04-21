#!/bin/bash
# demo_end_to_end.sh

echo "===== DEMO KỊCH BẢN END-TO-END: QUÁ TRÌNH ĐẶT HÀNG ĐẾN GIAO HÀNG ====="

# 1. Kiểm tra kho hàng trước khi đặt hàng
echo "BƯỚC 1: Kiểm tra kho hàng trước khi đặt hàng"
echo "Kiểm tra tồn kho sản phẩm PROD-001..."
curl -s "http://localhost:8000/inventory/PROD-001"
echo -e "\n\n"

# 2. Tạo đơn hàng mới
echo "BƯỚC 2: Tạo đơn hàng mới"
ORDER_RESPONSE=$(curl -s -X POST "http://localhost:8000/orders" -H "Content-Type: application/json" -d '{
  "customer_id": "CUST-001",
  "items": [
    {"product_id": "PROD-001", "quantity": 2, "price": 1299.99}
  ],
  "total_amount": 2599.98
}')
ORDER_ID=$(echo $ORDER_RESPONSE | grep -o '"id":"[^"]*' | sed 's/"id":"//')

echo "Đơn hàng đã được tạo với ID: $ORDER_ID"
echo "Trạng thái ban đầu của đơn hàng: CREATED"
echo -e "\n"

# 3. Phê duyệt đơn hàng
echo "BƯỚC 3: Phê duyệt đơn hàng"
echo "Gửi yêu cầu phê duyệt đơn hàng..."
curl -s -X POST "http://localhost:8000/orders/$ORDER_ID/approve"
echo -e "\n"

echo "Đang chờ 5 giây cho quá trình phê duyệt và xử lý..."
sleep 5

echo "Kiểm tra trạng thái đơn hàng sau khi phê duyệt..."
curl -s "http://localhost:8000/orders/$ORDER_ID/status"
echo -e "\n\n"

# 4. Kiểm tra tồn kho sau khi phê duyệt
echo "BƯỚC 4: Kiểm tra tồn kho sau khi phê duyệt"
echo "Kiểm tra tồn kho sản phẩm PROD-001 sau khi đặt trước..."
curl -s "http://localhost:8000/inventory/PROD-001"
echo -e "\n\n"

# 5. Xử lý thanh toán
echo "BƯỚC 5: Xử lý thanh toán"
echo "Tạo thanh toán cho đơn hàng..."
PAYMENT_RESPONSE=$(curl -s -X POST "http://localhost:8000/payments" -H "Content-Type: application/json" -d "{
  \"order_id\": \"$ORDER_ID\",
  \"amount\": 2599.98,
  \"payment_method\": \"credit_card\",
  \"payment_details\": {
    \"card_number\": \"xxxx-xxxx-xxxx-1234\",
    \"expiry\": \"12/25\"
  }
}")
PAYMENT_ID=$(echo $PAYMENT_RESPONSE | grep -o '"id":"[^"]*' | sed 's/"id":"//')

echo "Thanh toán đã được tạo với ID: $PAYMENT_ID"
echo -e "\n"

echo "Kiểm tra trạng thái thanh toán..."
curl -s "http://localhost:8000/payments/order/$ORDER_ID"
echo -e "\n\n"

# 6. Cập nhật thông tin vận chuyển
echo "BƯỚC 6: Cập nhật thông tin vận chuyển"
echo "Tạo đơn vận chuyển cho đơn hàng..."
curl -s -X POST "http://localhost:8000/shipping" -H "Content-Type: application/json" -d "{
  \"order_id\": \"$ORDER_ID\",
  \"status\": \"preparing\",
  \"address\": \"123 Main St, City\",
  \"tracking_number\": \"\"
}"
echo -e "\n"

echo "Đang chờ 3 giây để chuẩn bị đơn hàng..."
sleep 3

echo "Cập nhật trạng thái vận chuyển (đang vận chuyển)..."
curl -s -X PUT "http://localhost:8000/shipping/$ORDER_ID" -H "Content-Type: application/json" -d "{
  \"status\": \"shipped\",
  \"tracking_number\": \"TRACK-${ORDER_ID}\"
}"
echo -e "\n"

echo "Kiểm tra thông tin vận chuyển..."
curl -s "http://localhost:8000/shipping/order/$ORDER_ID"
echo -e "\n\n"

# 7. Kiểm tra trạng thái cuối cùng của đơn hàng
echo "BƯỚC 7: Kiểm tra trạng thái cuối cùng của đơn hàng"
echo "Trạng thái đơn hàng hiện tại..."
curl -s "http://localhost:8000/orders/$ORDER_ID/status"
echo -e "\n"

echo "Thông tin đầy đủ của đơn hàng..."
curl -s "http://localhost:8000/orders/$ORDER_ID"
echo -e "\n\n"

# 8. Kiểm tra trạng thái workflow
echo "BƯỚC 8: Kiểm tra Chuỗi Sự kiện của Workflow (Temporal)"
echo "Mở Temporal UI (http://localhost:8088) và tìm workflow với ID: $ORDER_ID"
echo "Để xem chi tiết quá trình xử lý và trạng thái workflow"
echo -e "\n"

echo "Demo kịch bản end-to-end đã hoàn tất." 