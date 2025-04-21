# Hệ thống Quản lý Đơn hàng Temporal

Đây là một dự án ví dụ về hệ thống quản lý đơn hàng sử dụng Temporal để điều phối quy trình nghiệp vụ phức tạp, FastAPI cho API, và Docker để quản lý các dịch vụ phụ thuộc. Dự án này minh họa các quy trình phê duyệt đơn hàng, xử lý thanh toán và quản lý kho hàng.

## Yêu cầu

*   Docker và Docker Compose (phiên bản mới nhất được khuyến nghị) hoặc Docker Desktop.
*   Python 3.9+.
*   `pip` và `venv` (hoặc công cụ quản lý môi trường ảo Python khác).

## Cài đặt và Chạy Hệ thống

1.  **Sao chép Repository:**
    ```bash
    git clone https://github.com/thanhmiyata/order_management_system
    cd order_management_system
    ```

2.  **Khởi chạy Backend Services (Temporal, Postgres):**
    Đảm bảo Docker đang chạy. Mở terminal trong thư mục gốc của dự án và chạy:
    ```bash
    docker compose up -d
    ```
    Lệnh này sẽ tải về các images cần thiết và khởi chạy Temporal Server, Temporal Web UI và PostgreSQL trong background.
    *   Bạn có thể truy cập Temporal Web UI tại: `http://localhost:8088`

3.  **Tạo và Kích hoạt Môi trường ảo Python:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
    *(Trên Windows, sử dụng: `venv\Scripts\activate`)*

4.  **Cài đặt Dependencies Python:**
    (Đảm bảo môi trường ảo đã được kích hoạt)
    ```bash
    pip install -r requirements.txt
    ```

5.  **Chạy Temporal Worker:**
    Mở một **terminal mới** (và kích hoạt lại venv: `source venv/bin/activate`), sau đó chạy:
    ```bash
    python worker.py
    ```
    Worker sẽ kết nối tới Temporal Server (chạy trong Docker) và lắng nghe các tasks trên task queue `order-task-queue`. **Giữ terminal này chạy.**

6.  **Chạy API Server (FastAPI):**
    Mở một **terminal mới khác** (và kích hoạt lại venv: `source venv/bin/activate`), sau đó chạy:
    ```bash
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    API server sẽ chạy tại `http://localhost:8000`. Cờ `--reload` giúp server tự khởi động lại khi có thay đổi trong code. **Giữ terminal này chạy.**

    *   Bạn có thể xem tài liệu API tương tác (Swagger UI) tại: `http://localhost:8000/docs`

## Chạy Kịch Bản Demo

Hệ thống này hỗ trợ ba quy trình workflow chính:

### 1. Quy trình Phê duyệt Đơn hàng (Order Approval)

Sau khi hoàn thành các bước cài đặt và cả 3 thành phần (Docker services, Worker, API Server) đều đang chạy, bạn có thể thực hiện kịch bản demo sau:

1.  **Quan sát Ban đầu:** Mở Temporal Web UI (`http://localhost:8088`) để chuẩn bị theo dõi.

2.  **Tạo Đơn Hàng Mới:**
    Sử dụng `curl` (hoặc Postman/Swagger UI) để gửi yêu cầu tạo đơn hàng:
    ```bash
    curl -X POST "http://localhost:8000/orders" -H "Content-Type: application/json" -d '{"customer_id": "CUST123", "items": [{"product_id": "PROD-001", "quantity": 1, "price": 1299.99}], "total_amount": 1299.99}'
    ```
    Ghi lại `order_id` (ví dụ: `order_abc123`) được trả về từ API.

3.  **Theo dõi Workflow trên UI (Validation):**
    *   Trên Temporal Web UI, tìm workflow tương ứng với `order_id`.
    *   Bạn sẽ thấy workflow khởi chạy và đi vào trạng thái `VALIDATION_PENDING`.
    *   (Nếu `validate_order` được code để giả lập lỗi) Bạn có thể thấy activity này thất bại và được Temporal tự động retry trong mục "History".

4.  **Theo dõi Workflow trên UI (Chờ Phê Duyệt):**
    *   Sau khi validation thành công, workflow chuyển sang trạng thái `PENDING_APPROVAL`.
    *   Kiểm tra log của **Worker terminal** để thấy thông báo "Notifying manager about pending approval for order...".
    *   Workflow sẽ dừng lại ở trạng thái này, chờ tín hiệu.
    *   Kiểm tra trạng thái qua API:
        ```bash
        curl http://localhost:8000/orders/{order_id}/status # Thay {order_id} bằng ID thực tế
        ```
        Kết quả trả về sẽ là: `{"status":"PENDING_APPROVAL"}`

5.  **Gửi Tín Hiệu Phê Duyệt hoặc Từ Chối (Chọn 1):**

    *   **Cách 1: Phê duyệt Đơn Hàng**
        ```bash
        curl -X POST http://localhost:8000/orders/{order_id}/approve # Thay {order_id}
        ```
        *   Quan sát UI: Workflow nhận tín hiệu, chạy activity `process_approved_order`, chuyển sang trạng thái `APPROVED` và hoàn thành (COMPLETED).
        *   Kiểm tra lại trạng thái qua API, kết quả sẽ là `APPROVED`.

    *   **Cách 2: Từ chối Đơn Hàng**
        ```bash
        curl -X POST http://localhost:8000/orders/{order_id}/reject # Thay {order_id}
        ```
        *   Quan sát UI: Workflow nhận tín hiệu, chạy `notify_rejection`, chuyển sang trạng thái `REJECTED` và hoàn thành.
        *   Kiểm tra lại trạng thái qua API, kết quả sẽ là `REJECTED`.

6.  **(Tùy chọn) Gửi Tín Hiệu Hủy:**
    Trong lúc workflow đang ở trạng thái `PENDING_APPROVAL`, bạn có thể thử hủy:
    ```bash
    curl -X POST http://localhost:8000/orders/{order_id}/cancel # Thay {order_id}
    ```
    *   Quan sát UI: Workflow sẽ nhận tín hiệu và chuyển sang trạng thái `CANCELLED`.

### 2. Quy trình Xử lý Thanh toán (Payment Processing)

Quy trình này xử lý việc thanh toán đơn hàng với các bước retry, xác thực và hoàn tiền (nếu cần):

1. **Tạo một yêu cầu thanh toán:**
   ```bash
   curl -X POST "http://localhost:8000/payments" -H "Content-Type: application/json" -d '{"order_id": "ORDER123", "amount": 1299.99, "method": "CREDIT_CARD"}'
   ```
   Ghi lại `payment_id` được trả về từ API.

2. **Theo dõi Workflow trên UI:**
   * Trên Temporal Web UI, tìm workflow thanh toán tương ứng.
   * Bạn sẽ thấy workflow xử lý thanh toán, có thể thực hiện retry nếu có lỗi tạm thời.

3. **Kiểm tra trạng thái thanh toán:**
   ```bash
   curl http://localhost:8000/payments/{payment_id}/status
   ```

4. **Yêu cầu hoàn tiền (nếu cần):**
   ```bash
   curl -X POST http://localhost:8000/payments/{payment_id}/refund
   ```
   * Workflow sẽ xử lý yêu cầu hoàn tiền và chuyển thanh toán sang trạng thái `REFUNDED`.

### 3. Quy trình Quản lý Kho hàng (Inventory Management)

Quy trình này quản lý việc kiểm tra, đặt trước và cập nhật kho hàng sử dụng mẫu Saga:

1. **Kiểm tra tồn kho cho một sản phẩm:**
   ```bash
   curl http://localhost:8000/inventory/PROD-001/check?quantity=5
   ```

2. **Đặt trước hàng tồn kho cho đơn hàng:**
   ```bash
   curl -X POST "http://localhost:8000/inventory/reserve" -H "Content-Type: application/json" -d '{"order_id": "ORDER123", "items": [{"product_id": "PROD-001", "quantity": 2}, {"product_id": "PROD-002", "quantity": 1}]}'
   ```
   Ghi lại `reservation_id` được trả về.

3. **Theo dõi Workflow trên UI:**
   * Tìm workflow quản lý kho hàng trên Temporal Web UI.
   * Bạn sẽ thấy workflow thực hiện mẫu Saga, đặt trước từng sản phẩm và đợi xác nhận.

4. **Xác nhận đặt trước (commit):**
   ```bash
   curl -X POST http://localhost:8000/inventory/commit/{reservation_id}
   ```
   * Workflow sẽ cập nhật kho hàng thực tế, giảm số lượng đã đặt trước.

5. **Hoặc hủy đặt trước (rollback):**
   ```bash
   curl -X POST http://localhost:8000/inventory/cancel/{reservation_id}
   ```
   * Workflow sẽ thực hiện rollback, hủy bỏ toàn bộ đặt trước đã thực hiện.

## Chạy Thử Nghiệm Hiệu Năng

Dự án này cũng bao gồm các thử nghiệm hiệu năng để so sánh Temporal với hệ thống truyền thống:

1. **Kích hoạt môi trường ảo và chạy thử nghiệm:**
   ```bash
   source venv/bin/activate
   python -m tests.performance_test
   ```

2. **Xem kết quả thử nghiệm:**
   Kết quả sẽ được hiển thị trong terminal và lưu vào file `performance_results_<timestamp>.txt`.

Thử nghiệm hiệu năng bao gồm:
* **Xử lý đồng thời:** So sánh khả năng xử lý nhiều đơn hàng cùng lúc.
* **Dữ liệu lớn:** So sánh khả năng xử lý đơn hàng có nhiều mục.

## API Endpoints Chính

### Order API
*   `POST /orders`: Tạo đơn hàng mới.
*   `GET /orders/{order_id}/status`: Lấy trạng thái hiện tại của đơn hàng.
*   `POST /orders/{order_id}/approve`: Gửi tín hiệu phê duyệt cho đơn hàng đang chờ.
*   `POST /orders/{order_id}/reject`: Gửi tín hiệu từ chối cho đơn hàng đang chờ.
*   `POST /orders/{order_id}/cancel`: Gửi tín hiệu hủy cho workflow đang chạy.

### Payment API
*   `POST /payments`: Tạo thanh toán mới.
*   `GET /payments/{payment_id}/status`: Lấy trạng thái hiện tại của thanh toán.
*   `POST /payments/{payment_id}/refund`: Yêu cầu hoàn tiền cho thanh toán.

### Inventory API
*   `GET /inventory/{product_id}/check`: Kiểm tra tồn kho cho sản phẩm.
*   `POST /inventory/reserve`: Đặt trước hàng tồn kho cho đơn hàng.
*   `POST /inventory/commit/{reservation_id}`: Xác nhận đặt trước.
*   `POST /inventory/cancel/{reservation_id}`: Hủy đặt trước.

## Cấu trúc Dự án

*   `api/`: Mã nguồn FastAPI (endpoints, client Temporal).
*   `workflows/`: Định nghĩa Temporal Workflows (OrderApprovalWorkflow, PaymentWorkflow, InventoryWorkflow).
*   `activities/`: Định nghĩa Temporal Activities cho từng domain.
*   `models/`: Pydantic data models (Order, Payment, Inventory).
*   `worker.py`: Script để chạy Temporal Worker, đăng ký tất cả workflows và activities.
*   `tests/`: Thử nghiệm hiệu năng và unit tests.
*   `requirements.txt`: Danh sách thư viện Python.
*   `docker-compose.yml`: Cấu hình Docker cho Temporal, Postgres, Temporal-Web.
*   `.env`: File cấu hình môi trường.
*   `README.md`: File này. 