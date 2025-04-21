#!/bin/bash
# demo_error_scenarios.sh

echo "===== DEMO CÁC TÌNH HUỐNG LỖI ====="

# 1. Tạo đơn hàng với sản phẩm không đủ tồn kho
echo "TÌNH HUỐNG 1: ĐẶT HÀNG VỚI SỐ LƯỢNG VƯỢT QUÁ TỒN KHO"
echo "Kiểm tra tồn kho sản phẩm PROD-002..."
curl -s "http://localhost:8000/inventory/PROD-002"
echo -e "\n"

echo "Đặt hàng với số lượng vượt quá tồn kho..."
curl -s -X POST "http://localhost:8000/orders" -H "Content-Type: application/json" -d '{
  "customer_id": "CUST-ERROR-1",
  "items": [
    {"product_id": "PROD-002", "quantity": 100, "price": 499.99}
  ],
  "total_amount": 49999.00
}'
echo -e "\n\n"


# 2. Thử phê duyệt đơn hàng không tồn tại
echo "TÌNH HUỐNG 2: PHÊ DUYỆT ĐƠN HÀNG KHÔNG TỒN TẠI"
echo "Phê duyệt đơn hàng với ID không tồn tại..."
curl -s -X POST "http://localhost:8000/orders/NON-EXISTENT-ORDER-ID/approve"
echo -e "\n\n"


# 3. Tạo thanh toán với số tiền không khớp
echo "TÌNH HUỐNG 3: THANH TOÁN VỚI SỐ TIỀN KHÔNG KHỚP"
echo "Tạo đơn hàng mới với giá trị 999.99..."
ORDER_RESPONSE=$(curl -s -X POST "http://localhost:8000/orders" -H "Content-Type: application/json" -d '{
  "customer_id": "CUST-ERROR-3",
  "items": [
    {"product_id": "PROD-003", "quantity": 1, "price": 999.99}
  ],
  "total_amount": 999.99
}')

ORDER_ID=$(echo $ORDER_RESPONSE | grep -o '"id":"[^"]*' | sed 's/"id":"//')
echo "Đơn hàng đã được tạo với ID: $ORDER_ID"
echo -e "\n"

echo "Tạo thanh toán với số tiền không chính xác..."
curl -s -X POST "http://localhost:8000/payments" -H "Content-Type: application/json" -d "{
  \"order_id\": \"$ORDER_ID\",
  \"amount\": 899.99,
  \"payment_method\": \"credit_card\",
  \"payment_details\": {
    \"card_number\": \"xxxx-xxxx-xxxx-5678\",
    \"expiry\": \"03/26\"
  }
}"
echo -e "\n\n"


# 4. Thử gửi hàng cho đơn chưa thanh toán
echo "TÌNH HUỐNG 4: GỬI HÀNG CHO ĐƠN CHƯA THANH TOÁN"
echo "Tạo đơn hàng mới..."
ORDER_RESPONSE=$(curl -s -X POST "http://localhost:8000/orders" -H "Content-Type: application/json" -d '{
  "customer_id": "CUST-ERROR-4",
  "items": [
    {"product_id": "PROD-001", "quantity": 1, "price": 1299.99}
  ],
  "total_amount": 1299.99
}')

ORDER_ID=$(echo $ORDER_RESPONSE | grep -o '"id":"[^"]*' | sed 's/"id":"//')
echo "Đơn hàng đã được tạo với ID: $ORDER_ID"
echo "Trạng thái: CREATED - chưa được phê duyệt hoặc thanh toán"
echo -e "\n"

echo "Thử tạo đơn vận chuyển cho đơn hàng chưa thanh toán..."
curl -s -X POST "http://localhost:8000/shipping" -H "Content-Type: application/json" -d "{
  \"order_id\": \"$ORDER_ID\",
  \"status\": \"shipped\",
  \"address\": \"456 Error St, City\",
  \"tracking_number\": \"TRACK-ERROR-${ORDER_ID}\"
}"
echo -e "\n\n"


# 5. Thử hủy đơn hàng đã được phê duyệt
echo "TÌNH HUỐNG 5: HỦY ĐƠN HÀNG ĐÃ ĐƯỢC PHÊ DUYỆT"
echo "Tạo đơn hàng mới..."
ORDER_RESPONSE=$(curl -s -X POST "http://localhost:8000/orders" -H "Content-Type: application/json" -d '{
  "customer_id": "CUST-ERROR-5",
  "items": [
    {"product_id": "PROD-003", "quantity": 1, "price": 349.99}
  ],
  "total_amount": 349.99
}')

ORDER_ID=$(echo $ORDER_RESPONSE | grep -o '"id":"[^"]*' | sed 's/"id":"//')
echo "Đơn hàng đã được tạo với ID: $ORDER_ID"
echo -e "\n"

echo "Phê duyệt đơn hàng..."
curl -s -X POST "http://localhost:8000/orders/$ORDER_ID/approve"
echo -e "\n"

echo "Đang chờ 5 giây để đơn hàng được xử lý..."
sleep 5

echo "Thử hủy đơn hàng đã phê duyệt..."
curl -s -X POST "http://localhost:8000/orders/$ORDER_ID/cancel"
echo -e "\n"

echo "Kiểm tra trạng thái đơn hàng..."
curl -s "http://localhost:8000/orders/$ORDER_ID/status"
echo -e "\n\n"


# 6. Kiểm tra xử lý lỗi workflow trong Temporal UI
echo "TÌNH HUỐNG 6: KIỂM TRA XỬ LÝ LỖI TRONG TEMPORAL"
echo "Mở Temporal UI (http://localhost:8088) để xem trạng thái các workflow và cách hệ thống xử lý các lỗi"
echo "Tìm kiếm các workflow có ID: $ORDER_ID hoặc workflow có lỗi để xem chi tiết"
echo -e "\n"

echo "Demo các tình huống lỗi đã hoàn tất." 