#!/bin/bash

# Script demo test hiệu năng
# Lưu ý: Đảm bảo đã chạy docker-compose, worker và API server trước khi chạy script này

echo "=== DEMO TEST HIỆU NĂNG ==="
echo "1. Test xử lý đồng thời"
echo "2. Test dữ liệu lớn"
echo "========================="

# Tạo thư mục kết quả nếu chưa tồn tại
mkdir -p performance_results

# 1. Test xử lý đồng thời
echo -e "\n=== 1. TEST XỬ LÝ ĐỒNG THỜI ==="
echo "Tạo 10 đơn hàng đồng thời..."
start_time=$(date +%s)

for i in {1..10}; do
  curl -s -X POST "http://localhost:8000/orders" \
    -H "Content-Type: application/json" \
    -d "{\"customer_id\": \"CUST$i\", \"items\": [{\"product_id\": \"PROD-00$i\", \"quantity\": 1, \"price\": 1299.99}], \"total_amount\": 1299.99}" &
done

wait
end_time=$(date +%s)
duration=$((end_time - start_time))
echo "Thời gian xử lý 10 đơn hàng đồng thời: $duration giây"

# 2. Test dữ liệu lớn
echo -e "\n=== 2. TEST DỮ LIỆU LỚN ==="
echo "Tạo đơn hàng với 100 sản phẩm..."
start_time=$(date +%s)

# Tạo mảng items với 100 sản phẩm
ITEMS="["
for i in {1..100}; do
  ITEMS+="{\"product_id\": \"PROD-$i\", \"quantity\": 1, \"price\": 1299.99}"
  if [ $i -lt 100 ]; then
    ITEMS+=","
  fi
done
ITEMS+="]"

curl -s -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d "{\"customer_id\": \"CUST-LARGE\", \"items\": $ITEMS, \"total_amount\": 129999.00}"

end_time=$(date +%s)
duration=$((end_time - start_time))
echo "Thời gian xử lý đơn hàng 100 sản phẩm: $duration giây"

# Lưu kết quả vào file
timestamp=$(date +%Y%m%d_%H%M%S)
echo "=== KẾT QUẢ TEST HIỆU NĂNG ===" > "performance_results/results_$timestamp.txt"
echo "Thời gian xử lý 10 đơn hàng đồng thời: $duration giây" >> "performance_results/results_$timestamp.txt"
echo "Thời gian xử lý đơn hàng 100 sản phẩm: $duration giây" >> "performance_results/results_$timestamp.txt"

echo -e "\nKết quả đã được lưu vào file: performance_results/results_$timestamp.txt"
echo -e "\n=== KẾT THÚC TEST HIỆU NĂNG ===" 