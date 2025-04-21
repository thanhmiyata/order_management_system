from temporalio import activity
from temporalio.exceptions import ApplicationError
import asyncio
import random
import sys
import os
from datetime import datetime

# Adjust the import path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.payment import Payment, PaymentStatus, PaymentMethod

async def _simulate_payment_gateway(payment_id: str, amount: float, method: PaymentMethod, duration_seconds: int = 2):
    """Mô phỏng gọi đến cổng thanh toán bên ngoài"""
    activity.logger.info(f"Connecting to payment gateway for payment {payment_id}, amount: ${amount:.2f}, method: {method}")
    await asyncio.sleep(duration_seconds)
    
    # Mô phỏng xác suất thành công dựa trên phương thức thanh toán
    success_rates = {
        PaymentMethod.CREDIT_CARD: 0.95,
        PaymentMethod.BANK_TRANSFER: 0.98,
        PaymentMethod.CASH: 1.0,
        PaymentMethod.E_WALLET: 0.90
    }
    
    success_chance = success_rates.get(method, 0.9)
    is_successful = random.random() < success_chance
    
    if not is_successful:
        activity.logger.error(f"Payment gateway declined transaction for payment {payment_id}")
        return None
    
    # Tạo mã giao dịch giả
    transaction_id = f"TXN-{random.randint(100000, 999999)}"
    activity.logger.info(f"Payment gateway approved transaction {transaction_id} for payment {payment_id}")
    return transaction_id

@activity.defn
async def process_payment(payment: dict) -> dict:
    """Xử lý thanh toán qua cổng thanh toán"""
    payment_obj = Payment(**payment)
    activity.logger.info(f"Processing payment {payment_obj.id} for order {payment_obj.order_id}")
    
    # Kiểm tra dữ liệu đầu vào
    if payment_obj.amount <= 0:
        raise ApplicationError("Payment amount must be positive", non_retryable=True)
    
    # Mô phỏng lỗi tạm thời (có thể retry)
    if random.random() < 0.3:  # 30% xác suất lỗi tạm thời
        activity.logger.warning(f"Temporary payment service failure for payment {payment_obj.id}")
        raise ValueError("Payment service temporarily unavailable")
    
    # Cập nhật trạng thái
    payment_obj.status = PaymentStatus.PROCESSING
    
    # Gọi đến cổng thanh toán
    transaction_id = await _simulate_payment_gateway(
        payment_obj.id, 
        payment_obj.amount, 
        payment_obj.method
    )
    
    if transaction_id:
        payment_obj.status = PaymentStatus.COMPLETED
        payment_obj.transaction_id = transaction_id
        payment_obj.updated_at = datetime.now()
        activity.logger.info(f"Payment {payment_obj.id} completed successfully with transaction {transaction_id}")
    else:
        payment_obj.status = PaymentStatus.FAILED
        payment_obj.updated_at = datetime.now()
        activity.logger.error(f"Payment {payment_obj.id} failed")
    
    # Trả về đối tượng payment đã cập nhật
    return payment_obj.to_dict()

@activity.defn
async def refund_payment(payment: dict) -> dict:
    """Hoàn tiền cho một giao dịch đã hoàn thành"""
    payment_obj = Payment(**payment)
    activity.logger.info(f"Processing refund for payment {payment_obj.id}, transaction {payment_obj.transaction_id}")
    
    # Kiểm tra xem thanh toán có thể hoàn lại không
    if payment_obj.status != PaymentStatus.COMPLETED:
        activity.logger.error(f"Cannot refund payment {payment_obj.id} with status {payment_obj.status}")
        raise ApplicationError(f"Cannot refund payment with status: {payment_obj.status}", non_retryable=True)
    
    if not payment_obj.transaction_id:
        activity.logger.error(f"Cannot refund payment {payment_obj.id} without transaction ID")
        raise ApplicationError("Cannot refund payment without transaction ID", non_retryable=True)
    
    # Mô phỏng gọi API hoàn tiền
    await asyncio.sleep(1.5)
    
    # Mô phỏng xác suất thành công hoàn tiền (95%)
    is_successful = random.random() < 0.95
    
    if is_successful:
        payment_obj.status = PaymentStatus.REFUNDED
        payment_obj.updated_at = datetime.now()
        payment_obj.description = f"Refunded payment. Original transaction: {payment_obj.transaction_id}"
        activity.logger.info(f"Refund processed successfully for payment {payment_obj.id}")
    else:
        activity.logger.error(f"Failed to process refund for payment {payment_obj.id}")
        raise ValueError("Payment gateway unable to process refund")
    
    return payment_obj.to_dict()

@activity.defn
async def verify_payment_status(payment_id: str, transaction_id: str) -> dict:
    """Kiểm tra trạng thái thanh toán với cổng thanh toán"""
    activity.logger.info(f"Verifying payment status for payment {payment_id}, transaction {transaction_id}")
    
    # Mô phỏng gọi API kiểm tra trạng thái
    await asyncio.sleep(1)
    
    # Mô phỏng kết quả
    status_options = [PaymentStatus.COMPLETED, PaymentStatus.FAILED, PaymentStatus.PROCESSING]
    weights = [0.85, 0.1, 0.05]  # 85% hoàn thành, 10% thất bại, 5% đang xử lý
    
    status = random.choices(status_options, weights=weights)[0]
    
    activity.logger.info(f"Payment {payment_id} verification result: {status}")
    
    return {
        "payment_id": payment_id,
        "transaction_id": transaction_id,
        "status": status,
        "verified_at": datetime.now().isoformat()
    }

# Tất cả các activities thanh toán
payment_activities = [
    process_payment,
    refund_payment,
    verify_payment_status
] 