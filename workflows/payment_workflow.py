from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, CancelledError
from datetime import timedelta
import sys
import os
import asyncio

# Adjust the import path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.payment import Payment, PaymentStatus

# Define activities stub
with workflow.unsafe.imports_passed_through():
    from activities.payment_activities import process_payment, refund_payment, verify_payment_status

@workflow.defn
class PaymentWorkflow:
    def __init__(self):
        self._payment_state = None
        self._is_cancelled = False
        self._refund_requested = False
        
        # Define RetryPolicy
        self._payment_retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
            non_retryable_error_types=["ApplicationError"],
        )

    @workflow.run
    async def run(self, payment_input: dict):
        self._payment_state = Payment(**payment_input)
        workflow.logger.info(f"Starting PaymentWorkflow for payment: {self._payment_state.id}, order: {self._payment_state.order_id}")

        try:
            # 1. Xử lý thanh toán
            workflow.logger.info(f"Processing payment {self._payment_state.id}")
            try:
                payment_result = await workflow.start_activity(
                    process_payment,
                    self._payment_state.to_dict(),
                    retry_policy=self._payment_retry_policy,
                    start_to_close_timeout=timedelta(seconds=30),
                )
                # Cập nhật trạng thái thanh toán
                self._payment_state = Payment(**payment_result)
                workflow.logger.info(f"Payment {self._payment_state.id} processed, status: {self._payment_state.status}")
            
            except ApplicationError as e:
                # Lỗi không thể retry (dữ liệu không hợp lệ)
                workflow.logger.error(f"Payment {self._payment_state.id} failed due to validation error: {e}")
                self._payment_state.status = PaymentStatus.FAILED
                return self._payment_state.to_dict()
            
            except ActivityError as e:
                # Lỗi sau khi đã retry hết số lần cho phép
                workflow.logger.error(f"Payment {self._payment_state.id} failed after retries: {e}")
                self._payment_state.status = PaymentStatus.FAILED
                return self._payment_state.to_dict()
            
            except CancelledError:
                workflow.logger.info(f"Payment workflow cancelled during processing for {self._payment_state.id}")
                raise
            
            # 2. Đợi xác nhận thanh toán nếu cần thiết (nếu đang trong trạng thái PROCESSING)
            if self._payment_state.status == PaymentStatus.PROCESSING:
                workflow.logger.info(f"Verifying payment status for {self._payment_state.id}")
                try:
                    verification_result = await workflow.start_activity(
                        verify_payment_status,
                        self._payment_state.id,
                        self._payment_state.transaction_id or "UNKNOWN",
                        start_to_close_timeout=timedelta(seconds=20),
                    )
                    
                    # Cập nhật trạng thái
                    self._payment_state.status = verification_result["status"]
                    workflow.logger.info(f"Payment {self._payment_state.id} verification completed, status: {self._payment_state.status}")
                
                except Exception as e:
                    workflow.logger.error(f"Failed to verify payment {self._payment_state.id}: {e}")
                    # Giữ nguyên trạng thái PROCESSING
            
            # 3. Đợi yêu cầu hoàn tiền nếu thanh toán đã hoàn thành
            if self._payment_state.status == PaymentStatus.COMPLETED:
                try:
                    # Đợi có hạn chế 1 ngày
                    refund_timeout = timedelta(days=1)
                    with workflow.timeout(refund_timeout):
                        await workflow.wait_condition(lambda: self._refund_requested)
                        
                        if self._refund_requested:
                            workflow.logger.info(f"Processing refund for payment {self._payment_state.id}")
                            try:
                                refund_result = await workflow.start_activity(
                                    refund_payment,
                                    self._payment_state.to_dict(),
                                    start_to_close_timeout=timedelta(seconds=30),
                                )
                                # Cập nhật trạng thái
                                self._payment_state = Payment(**refund_result)
                                workflow.logger.info(f"Refund for payment {self._payment_state.id} processed, status: {self._payment_state.status}")
                            
                            except Exception as e:
                                workflow.logger.error(f"Failed to process refund for payment {self._payment_state.id}: {e}")
                                # Không thay đổi trạng thái, vẫn là COMPLETED
                
                except workflow.CancelledError:
                    workflow.logger.info(f"Payment workflow cancelled while waiting for refund for {self._payment_state.id}")
                    raise
                
                except workflow.TimeoutError:
                    workflow.logger.info(f"Refund waiting period expired for payment {self._payment_state.id}")
                    # Thanh toán hoàn tất, không có hoàn tiền

        except Exception as e:
            # Bắt các lỗi không mong đợi
            workflow.logger.exception(f"Unhandled error in payment workflow for payment {self._payment_state.id}: {e}")
            if not self._is_cancelled:
                self._payment_state.status = PaymentStatus.FAILED
            raise
        
        workflow.logger.info(f"Payment workflow completed for payment {self._payment_state.id} with final status {self._payment_state.status}")
        return self._payment_state.to_dict()

    @workflow.query
    def get_status(self) -> str:
        """Trả về trạng thái hiện tại của thanh toán"""
        if not self._payment_state:
            return "UNKNOWN"
        return self._payment_state.status.value

    @workflow.query
    def get_details(self) -> dict:
        """Trả về toàn bộ thông tin thanh toán"""
        if not self._payment_state:
            return {}
        return self._payment_state.to_dict()

    @workflow.signal
    async def request_refund(self):
        """Tín hiệu yêu cầu hoàn tiền"""
        workflow.logger.info(f"Received refund request for payment {self._payment_state.id if self._payment_state else 'N/A'}")
        
        if not self._payment_state or self._payment_state.status != PaymentStatus.COMPLETED:
            workflow.logger.warning(f"Cannot refund payment that is not in COMPLETED state. Current status: {self._payment_state.status if self._payment_state else 'UNKNOWN'}")
            return
        
        self._refund_requested = True

    @workflow.signal
    async def cancel_payment(self):
        """Tín hiệu hủy workflow thanh toán"""
        workflow.logger.info(f"Received cancel signal for payment {self._payment_state.id if self._payment_state else 'N/A'}")
        self._is_cancelled = True 