#!/bin/bash
# demo_individual_features.sh

echo "===== DEMO CÁC TÍNH NĂNG RIÊNG LẺ ====="

# 1. Kiểm tra tồn kho
echo "TÍNH NĂNG 1: KIỂM TRA TỒN KHO"
echo "Kiểm tra tồn kho sản phẩm PROD-001..."
curl -s "http://localhost:8000/inventory/PROD-001"
echo -e "\n"

echo "Kiểm tra tồn kho sản phẩm PROD-002..."
curl -s "http://localhost:8000/inventory/PROD-002"
echo -e "\n"

echo "Kiểm tra tồn kho sản phẩm PROD-003..."
curl -s "http://localhost:8000/inventory/PROD-003"
echo -e "\n\n"


# 2. Tạo đơn hàng mới
echo "TÍNH NĂNG 2: TẠO ĐƠN HÀNG MỚI"
echo "Tạo đơn hàng mới..."
ORDER_RESPONSE=$(curl -s -X POST "http://localhost:8000/orders" -H "Content-Type: application/json" -d '{
  "customer_id": "CUST-001",
  "items": [
    {"product_id": "PROD-001", "quantity": 1, "price": 1299.99}
  ],
  "total_amount": 1299.99
}')

ORDER_ID=$(echo $ORDER_RESPONSE | grep -o '"id":"[^"]*' | sed 's/"id":"//')
echo "Đơn hàng đã được tạo với ID: $ORDER_ID"
echo -e "\n"

echo "Kiểm tra trạng thái đơn hàng..."
curl -s "http://localhost:8000/orders/$ORDER_ID/status"
echo -e "\n\n"


# 3. Phê duyệt đơn hàng
echo "TÍNH NĂNG 3: PHÊ DUYỆT ĐƠN HÀNG"
echo "Phê duyệt đơn hàng..."
curl -s -X POST "http://localhost:8000/orders/$ORDER_ID/approve"
echo -e "\n"

echo "Đang chờ 3 giây để đơn hàng được xử lý..."
sleep 3

echo "Kiểm tra trạng thái đơn hàng sau khi phê duyệt..."
curl -s "http://localhost:8000/orders/$ORDER_ID/status"
echo -e "\n\n"


# 4. Xử lý thanh toán
echo "TÍNH NĂNG 4: XỬ LÝ THANH TOÁN"
echo "Tạo thanh toán cho đơn hàng..."
PAYMENT_RESPONSE=$(curl -s -X POST "http://localhost:8000/payments" -H "Content-Type: application/json" -d "{
  \"order_id\": \"$ORDER_ID\",
  \"amount\": 1299.99,
  \"payment_method\": \"credit_card\",
  \"payment_details\": {
    \"card_number\": \"xxxx-xxxx-xxxx-1234\",
    \"expiry\": \"12/25\"
  }
}")

PAYMENT_ID=$(echo $PAYMENT_RESPONSE | grep -o '"id":"[^"]*' | sed 's/"id":"//')
echo "Thanh toán đã được tạo với ID: $PAYMENT_ID"
echo -e "\n"

echo "Đang chờ 3 giây để thanh toán được xử lý..."
sleep 3

echo "Kiểm tra trạng thái đơn hàng sau khi thanh toán..."
curl -s "http://localhost:8000/orders/$ORDER_ID/status"
echo -e "\n\n"


# 5. Cập nhật thông tin vận chuyển
echo "TÍNH NĂNG 5: CẬP NHẬT THÔNG TIN VẬN CHUYỂN"
echo "Tạo thông tin vận chuyển cho đơn hàng..."
SHIPPING_RESPONSE=$(curl -s -X POST "http://localhost:8000/shipping" -H "Content-Type: application/json" -d "{
  \"order_id\": \"$ORDER_ID\",
  \"status\": \"processing\",
  \"address\": \"123 Test St, Sample City\",
  \"tracking_number\": \"TRACK-$ORDER_ID\"
}")

echo "Thông tin vận chuyển đã được tạo."
echo -e "\n"

echo "Đang chờ 3 giây..."
sleep 3

echo "Cập nhật trạng thái vận chuyển sang 'shipped'..."
curl -s -X PUT "http://localhost:8000/shipping/$ORDER_ID" -H "Content-Type: application/json" -d "{
  \"status\": \"shipped\",
  \"tracking_number\": \"TRACK-$ORDER_ID\"
}"
echo -e "\n"

echo "Kiểm tra trạng thái đơn hàng sau khi cập nhật vận chuyển..."
curl -s "http://localhost:8000/orders/$ORDER_ID/status"
echo -e "\n\n"


# 6. Quản lý tồn kho
echo "TÍNH NĂNG 6: QUẢN LÝ TỒN KHO"
echo "Kiểm tra tồn kho sản phẩm PROD-001 trước khi cập nhật..."
curl -s "http://localhost:8000/inventory/PROD-001"
echo -e "\n"

echo "Cập nhật tồn kho (thêm 5 sản phẩm)..."
curl -s -X PUT "http://localhost:8000/inventory/PROD-001" -H "Content-Type: application/json" -d '{
  "quantity_change": 5,
  "reason": "restock"
}'
echo -e "\n"

echo "Kiểm tra tồn kho sau khi cập nhật..."
curl -s "http://localhost:8000/inventory/PROD-001"
echo -e "\n\n"


# 7. Truy vấn lịch sử đơn hàng
echo "TÍNH NĂNG 7: TRUY VẤN LỊCH SỬ ĐƠN HÀNG"
echo "Lấy chi tiết đơn hàng và lịch sử..."
curl -s "http://localhost:8000/orders/$ORDER_ID"
echo -e "\n\n"


# 8. Quản lý hồ sơ khách hàng
echo "TÍNH NĂNG 8: QUẢN LÝ HỒ SƠ KHÁCH HÀNG"
echo "Tạo hồ sơ khách hàng mới..."
CUSTOMER_RESPONSE=$(curl -s -X POST "http://localhost:8000/customers" -H "Content-Type: application/json" -d '{
  "name": "John Doe",
  "email": "john.doe@example.com",
  "phone": "123-456-7890",
  "address": "789 Customer St, City"
}')

CUSTOMER_ID=$(echo $CUSTOMER_RESPONSE | grep -o '"id":"[^"]*' | sed 's/"id":"//')
echo "Khách hàng đã được tạo với ID: $CUSTOMER_ID"
echo -e "\n"

echo "Lấy thông tin khách hàng..."
curl -s "http://localhost:8000/customers/$CUSTOMER_ID"
echo -e "\n\n"


# 9. Kiểm tra Temporal UI
echo "TÍNH NĂNG 9: KIỂM TRA TEMPORAL UI"
echo "Mở Temporal UI trong trình duyệt: http://localhost:8088"
echo "Tìm kiếm workflow với ID đơn hàng: $ORDER_ID"
echo -e "\n"

echo "Demo các tính năng riêng lẻ đã hoàn tất." 