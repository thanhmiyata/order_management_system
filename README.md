# Hệ thống Quản lý Đơn hàng Temporal

Một dự án ví dụ về hệ thống quản lý đơn hàng sử dụng Temporal để điều phối quy trình nghiệp vụ phức tạp, FastAPI cho API, và Docker để quản lý các dịch vụ phụ thuộc. Dự án minh họa các quy trình phê duyệt đơn hàng, xử lý thanh toán, quản lý kho hàng, và so sánh hiệu năng với cách tiếp cận truyền thống.

## Mục lục

*   [Yêu cầu](#yêu-cầu)
*   [Cài đặt](#cài-đặt)
*   [Chạy Hệ thống](#chạy-hệ-thống)
*   [Kịch bản Demo](#kịch-bản-demo)
    *   [Quy trình Phê duyệt Đơn hàng](#1-quy-trình-phê-duyệt-đơn-hàng-order-approval)
    *   [Quy trình Xử lý Thanh toán](#2-quy-trình-xử-lý-thanh-toán-payment-processing)
    *   [Quy trình Quản lý Kho hàng](#3-quy-trình-quản-lý-kho-hàng-inventory-management)
    *   [Video Demo Scripts](#video-demo-scripts)
*   [Chạy Thử nghiệm Hiệu năng](#chạy-thử-nghiệm-hiệu-năng)
*   [API Endpoints Chính](#api-endpoints-chính)
*   [Cấu trúc Dự án](#cấu-trúc-dự-án)

## Yêu cầu

*   Docker và Docker Compose (phiên bản mới nhất được khuyến nghị) hoặc Docker Desktop.
*   Python 3.9+.
*   `pip` và `venv` (hoặc công cụ quản lý môi trường ảo Python khác).

## Cài đặt

1.  **Sao chép Repository:**
    ```bash
    git clone https://github.com/thanhmiyata/order_management_system
    cd order_management_system
    ```

2.  **Tạo và Kích hoạt Môi trường ảo Python:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    # (Trên Windows: venv\Scripts\activate)
    ```

3.  **Cài đặt Dependencies Python:**
    (Đảm bảo môi trường ảo đã được kích hoạt)
    ```bash
    pip install -r requirements.txt
    ```

## Chạy Hệ thống

1.  **Khởi chạy Backend Services (Temporal, Postgres):**
    Đảm bảo Docker đang chạy. Mở terminal trong thư mục gốc của dự án và chạy:
    ```bash
    docker compose up -d
    ```
    Lệnh này sẽ tải về các images cần thiết và khởi chạy Temporal Server, Temporal Web UI và PostgreSQL trong background.
    *   Temporal Web UI: `http://localhost:8088`
    *   Để dừng các service: `docker compose down`

2.  **Chạy Temporal Worker:**
    Mở một **terminal mới** (và kích hoạt lại venv), sau đó chạy:
    ```bash
    python worker.py
    ```
    Worker sẽ kết nối tới Temporal Server và lắng nghe các tasks trên các task queue được định nghĩa. **Giữ terminal này chạy.**

3.  **Chạy API Server (FastAPI):**
    Mở một **terminal mới khác** (và kích hoạt lại venv), sau đó chạy:
    ```bash
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    API server sẽ chạy tại `http://localhost:8000`. Cờ `--reload` giúp server tự khởi động lại khi có thay đổi trong code. **Giữ terminal này chạy.**
    *   API Docs (Swagger UI): `http://localhost:8000/docs`

## Kịch bản Demo

Sau khi hoàn thành các bước cài đặt và cả 3 thành phần (Docker services, Worker, API Server) đều đang chạy, bạn có thể thực hiện các kịch bản demo sau:

### 1. Quy trình Phê duyệt Đơn hàng (Order Approval)

1.  **Quan sát Ban đầu:** Mở Temporal Web UI (`http://localhost:8088`).
2.  **Tạo Đơn Hàng Mới:**
    ```bash
    curl -X POST "http://localhost:8000/orders" -H "Content-Type: application/json" -d '{"customer_id": "CUST123", "items": [{"product_id": "PROD-001", "quantity": 1, "price": 1299.99}], "total_amount": 1299.99}'
    ```
    Ghi lại `order_id` (ví dụ: `order_abc123`).
3.  **Theo dõi Workflow trên UI:** Xem workflow chuyển trạng thái (VALIDATION_PENDING -> PENDING_APPROVAL).
4.  **Kiểm tra trạng thái:** `curl http://localhost:8000/orders/{order_id}/status`
5.  **Gửi Tín Hiệu:**
    *   Phê duyệt: `curl -X POST http://localhost:8000/orders/{order_id}/approve`
    *   Từ chối: `curl -X POST http://localhost:8000/orders/{order_id}/reject`
    *   Hủy (khi đang PENDING_APPROVAL): `curl -X POST http://localhost:8000/orders/{order_id}/cancel`
6.  **Quan sát Workflow hoàn thành** trên UI và kiểm tra lại trạng thái qua API.

### 2. Quy trình Xử lý Thanh toán (Payment Processing)

1.  **Tạo yêu cầu thanh toán:**
    ```bash
    curl -X POST "http://localhost:8000/payments" -H "Content-Type: application/json" -d '{"order_id": "ORDER123", "amount": 1299.99, "method": "CREDIT_CARD"}'
    ```
    Ghi lại `payment_id`.
2.  **Theo dõi Workflow trên UI:** Quan sát các bước xử lý, retry (nếu có).
3.  **Kiểm tra trạng thái:** `curl http://localhost:8000/payments/{payment_id}/status`
4.  **(Tùy chọn) Yêu cầu hoàn tiền:** `curl -X POST http://localhost:8000/payments/{payment_id}/refund`

### 3. Quy trình Quản lý Kho hàng (Inventory Management)

1.  **Kiểm tra tồn kho:** `curl http://localhost:8000/inventory/PROD-001/check?quantity=5`
2.  **Đặt trước hàng (Reserve - Saga):**
    ```bash
    curl -X POST "http://localhost:8000/inventory/reserve" -H "Content-Type: application/json" -d '{"order_id": "ORDER123", "items": [{"product_id": "PROD-001", "quantity": 2}, {"product_id": "PROD-002", "quantity": 1}]}'
    ```
    Ghi lại `reservation_id`.
3.  **Theo dõi Workflow trên UI:** Xem các bước đặt trước và activity đền bù (compensation).
4.  **Gửi Tín Hiệu:**
    *   Xác nhận (Commit): `curl -X POST http://localhost:8000/inventory/commit/{reservation_id}`
    *   Hủy (Rollback): `curl -X POST http://localhost:8000/inventory/cancel/{reservation_id}`

### Video Demo Scripts

Thư mục `Demo/` chứa các file kịch bản (`.txt`) chi tiết cho việc quay video demo các tính năng:
*   `video1_script.txt`: Demo luồng cơ bản.
*   `video2_script.txt`: Demo xử lý lỗi và rollback.

## Chạy Thử nghiệm Hiệu năng

Dự án bao gồm các thử nghiệm hiệu năng trong thư mục `tests/` để so sánh hiệu năng của kiến trúc dựa trên Temporal với một hệ thống truyền thống được mô phỏng.

1.  **Đảm bảo môi trường đang chạy:** Docker services, Worker, và API Server phải đang hoạt động.
2.  **Kích hoạt môi trường ảo** (nếu chưa): `source venv/bin/activate`
3.  **Chạy tất cả các bài test hiệu năng:**
    Mở terminal trong thư mục gốc của dự án và chạy:
    ```bash
    cd tests && python fair_performance_test.py && python simplified_performance_test.py && python performance_test.py && cd ..
    ```
    *(Lưu ý: `performance_test.py` trong trạng thái gốc có thể chạy khá lâu do mô phỏng độ trễ của hệ thống truyền thống.)*

4.  **Xem kết quả thử nghiệm:**
    Kết quả tóm tắt sẽ được hiển thị trong terminal sau khi mỗi file test chạy xong. Kết quả chi tiết được lưu vào các file `.txt` trong thư mục `tests/` (ví dụ: `fair_performance_results_<timestamp>.txt`, `simplified_performance_results_<timestamp>.txt`, `performance_results_<timestamp>.txt`).

Các bài test tập trung vào:
*   **Xử lý đồng thời:** So sánh khả năng xử lý nhiều đơn hàng cùng lúc.
*   **Dữ liệu lớn:** So sánh khả năng xử lý đơn hàng có nhiều mục (items).

## API Endpoints Chính

(Tham khảo API Docs tại `http://localhost:8000/docs` để biết chi tiết đầy đủ)

### Order API
*   `POST /orders`: Tạo đơn hàng mới.
*   `GET /orders/{order_id}/status`: Lấy trạng thái đơn hàng.
*   `POST /orders/{order_id}/approve`: Phê duyệt đơn hàng.
*   `POST /orders/{order_id}/reject`: Từ chối đơn hàng.
*   `POST /orders/{order_id}/cancel`: Hủy đơn hàng.

### Payment API
*   `POST /payments`: Tạo thanh toán mới.
*   `GET /payments/{payment_id}/status`: Lấy trạng thái thanh toán.
*   `POST /payments/{payment_id}/refund`: Yêu cầu hoàn tiền.

### Inventory API
*   `GET /inventory/{product_id}/check`: Kiểm tra tồn kho.
*   `POST /inventory/reserve`: Đặt trước hàng tồn kho (Saga).
*   `POST /inventory/commit/{reservation_id}`: Xác nhận đặt trước.
*   `POST /inventory/cancel/{reservation_id}`: Hủy đặt trước (Rollback Saga).
*   `GET /inventory/status/{reservation_id}`: Kiểm tra trạng thái của reservation workflow.
*   `POST /inventory/update`: (Có thể dùng cho test) Cập nhật trực tiếp số lượng tồn kho.

## Cấu trúc Dự án

*   `api/`: Mã nguồn FastAPI (endpoints, client Temporal).
*   `workflows/`: Định nghĩa Temporal Workflows (OrderApprovalWorkflow, PaymentWorkflow, InventoryWorkflow).
*   `activities/`: Định nghĩa Temporal Activities.
*   `models/`: Pydantic data models.
*   `worker.py`: Script chạy Temporal Worker.
*   `tests/`: Thử nghiệm hiệu năng (so sánh Temporal vs Traditional).
*   `Demo/`: Các file kịch bản (`.txt`) cho video demo.
*   `requirements.txt`: Dependencies Python.
*   `docker-compose.yml`: Cấu hình Docker cho Temporal, Postgres, Temporal-Web.
*   `.env`: File cấu hình môi trường.
*   `README.md`: File này. 