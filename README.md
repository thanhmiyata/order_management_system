# Hệ thống Quản lý Đơn hàng Temporal

Đây là một dự án ví dụ về hệ thống quản lý đơn hàng sử dụng Temporal để điều phối quy trình nghiệp vụ phức tạp, FastAPI cho API, và Docker để quản lý các dịch vụ phụ thuộc. Dự án này minh họa quy trình phê duyệt đơn hàng nâng cao.

## Yêu cầu

*   Docker và Docker Compose (phiên bản mới nhất được khuyến nghị) hoặc Docker Desktop.
*   Python 3.9+.
*   `pip` và `venv` (hoặc công cụ quản lý môi trường ảo Python khác).

## Cài đặt và Chạy Hệ thống

1.  **Sao chép Repository:**
    ```bash
    git clone <your-repo-url> # Thay bằng URL repo của bạn
    cd order_management_system
    ```

2.  **Khởi chạy Backend Services (Temporal, Postgres, Redis):**
    Đảm bảo Docker đang chạy. Mở terminal trong thư mục gốc của dự án và chạy:
    ```bash
    docker compose up -d
    ```
    Lệnh này sẽ tải về các images cần thiết và khởi chạy Temporal Server, Temporal Web UI, PostgreSQL và Redis trong background.
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

## Chạy Kịch Bản Demo (Advanced Order Approval)

Sau khi hoàn thành các bước trên và cả 3 thành phần (Docker services, Worker, API Server) đều đang chạy, bạn có thể thực hiện kịch bản demo sau:

1.  **Quan sát Ban đầu:** Mở Temporal Web UI (`http://localhost:8088`) để chuẩn bị theo dõi.

2.  **Tạo Đơn Hàng Mới:**
    Sử dụng `curl` (hoặc Postman/Swagger UI) để gửi yêu cầu tạo đơn hàng:
    ```bash
    curl -X POST "http://localhost:8000/orders" -H "Content-Type: application/json" -d '{"item": "Laptop Gaming XYZ", "quantity": 1}'
    ```
    Ghi lại `order_id` (ví dụ: `order_abc123`) được trả về từ API.

3.  **Theo dõi Workflow trên UI (Validation):**
    *   Trên Temporal Web UI, tìm workflow tương ứng với `order_id`.
    *   Bạn sẽ thấy workflow khởi chạy và đi vào trạng thái `VALIDATING`.
    *   (Nếu `validate_order` được code để giả lập lỗi) Bạn có thể thấy activity này thất bại và được Temporal tự động retry trong mục "History".

4.  **Theo dõi Workflow trên UI (Chờ Phê Duyệt):**
    *   Sau khi validation thành công, workflow chuyển sang trạng thái `PENDING_APPROVAL`.
    *   Kiểm tra log của **Worker terminal** để thấy thông báo "Notifying manager about order...".
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
        *   Quan sát UI: Workflow nhận tín hiệu, (chạy `process_rejected_order` nếu có), chuyển sang trạng thái `REJECTED` và hoàn thành.
        *   Kiểm tra lại trạng thái qua API, kết quả sẽ là `REJECTED`.

6.  **(Tùy chọn) Gửi Tín Hiệu Hủy:**
    Trong lúc workflow đang ở trạng thái `PENDING_APPROVAL`, bạn có thể thử hủy:
    ```bash
    curl -X POST http://localhost:8000/orders/{order_id}/cancel # Thay {order_id}
    ```
    *   Quan sát UI: Workflow sẽ nhận tín hiệu và chuyển sang trạng thái `CANCELLED`.

## API Endpoints Chính

*   `POST /orders`: Tạo đơn hàng mới.
    *   Body: `{"item": "string", "quantity": integer}`
*   `GET /orders/{order_id}/status`: Lấy trạng thái hiện tại của đơn hàng.
*   `POST /orders/{order_id}/approve`: Gửi tín hiệu phê duyệt cho đơn hàng đang chờ.
*   `POST /orders/{order_id}/reject`: Gửi tín hiệu từ chối cho đơn hàng đang chờ.
*   `POST /orders/{order_id}/cancel`: Gửi tín hiệu hủy cho workflow đang chạy.

## Cấu trúc Dự án

*   `api/`: Mã nguồn FastAPI (endpoints, client Temporal).
*   `workflows/`: Định nghĩa Temporal Workflow (`OrderApprovalWorkflow`).
*   `activities/`: Định nghĩa Temporal Activities (validation, notification, processing).
*   `models/`: Pydantic data models (`Order`, `OrderStatus`).
*   `worker.py`: Script để chạy Temporal Worker.
*   `requirements.txt`: Danh sách thư viện Python.
*   `docker-compose.yml`: Cấu hình Docker cho Temporal, Postgres, Redis, Temporal-Web.
*   `.env` (tùy chọn): File cấu hình môi trường (ít dùng hơn khi có Docker Compose).
*   `README.md`: File này. 