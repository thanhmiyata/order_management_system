from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, CancelledError, TimeoutError
from datetime import timedelta
import sys
import os
import asyncio
from typing import List, Dict

# Adjust the import path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.inventory import InventoryUpdate, InventoryStatus

# Define activities stub
with workflow.unsafe.imports_passed_through():
    from activities.inventory_activities import check_inventory, reserve_inventory, update_inventory, unreserve_inventory

@workflow.defn(name="InventoryWorkflow")
class InventoryWorkflow:
    def __init__(self):
        self._inventory_updates = []
        self._is_cancelled = False
        self._reservation_results = {}
        self._is_committed = False
        self._current_status = "PENDING"
        
        # Define RetryPolicy
        self._inventory_retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
            non_retryable_error_types=["ApplicationError"],
        )

    @workflow.run
    async def run(self, order_id: str, inventory_updates: List[Dict]):
        """
        Workflow quản lý kho hàng với mẫu Saga
        """
        workflow.logger.info(f"Starting InventoryWorkflow for order: {order_id} with {len(inventory_updates)} product updates")
        
        # Chuyển đổi từ dict sang InventoryUpdate để thêm order_id
        self._inventory_updates = []
        for update in inventory_updates:
            # Tạo một bản sao của update để không ảnh hưởng đến dữ liệu gốc
            update_copy = update.copy()
            # Chỉ thêm order_id nếu nó chưa tồn tại
            if 'order_id' not in update_copy:
                update_copy['order_id'] = order_id
            self._inventory_updates.append(InventoryUpdate(**update_copy).to_dict())
        
        try:
            # Kiểm tra xem đây là yêu cầu kiểm tra đơn thuần hay cập nhật tồn kho
            is_check_only = order_id.startswith("inventory_check_")
            
            # 1. Kiểm tra tồn kho cho tất cả sản phẩm
            check_results = {}
            for update in self._inventory_updates:
                product_id = update["product_id"]
                quantity = abs(update["quantity_change"])  # Đảm bảo lấy giá trị dương
                
                try:
                    result = await workflow.start_activity(
                        check_inventory,
                        args=[product_id, quantity],  # Pass arguments as a list
                        retry_policy=self._inventory_retry_policy,
                        start_to_close_timeout=timedelta(seconds=10),
                    )
                    check_results[product_id] = result
                    
                    if not result["is_available"]:
                        self._current_status = "FAILED"
                        workflow.logger.warning(f"Insufficient inventory for product {product_id} in order {order_id}")
                        return {
                            "order_id": order_id,
                            "status": "FAILED",
                            "reason": f"Insufficient inventory for product {product_id}",
                            "details": check_results
                        }
                
                except ApplicationError as e:
                    self._current_status = "FAILED"
                    workflow.logger.error(f"Inventory check failed for product {product_id} in order {order_id}: {e}")
                    return {
                        "order_id": order_id,
                        "status": "FAILED",
                        "reason": str(e),
                        "details": check_results
                    }
                
                except ActivityError as e:
                    self._current_status = "FAILED"
                    workflow.logger.error(f"Inventory check failed after retries for product {product_id} in order {order_id}: {e}")
                    return {
                        "order_id": order_id,
                        "status": "FAILED",
                        "reason": "Service unavailable",
                        "details": check_results
                    }
            
            # Nếu chỉ là kiểm tra tồn kho, trả về kết quả ngay
            if is_check_only:
                self._current_status = "COMPLETED"
                return {
                    "order_id": order_id,
                    "status": "COMPLETED",
                    "details": check_results
                }
            
            # 2. Đặt trước tồn kho cho tất cả sản phẩm (Saga pattern)
            reserved_products = []
            try:
                for update in self._inventory_updates:
                    product_id = update["product_id"]
                    
                    try:
                        reserve_result = await workflow.start_activity(
                            reserve_inventory,
                            args=[update],  # Pass arguments as a list
                            retry_policy=self._inventory_retry_policy,
                            start_to_close_timeout=timedelta(seconds=15),
                        )
                        self._reservation_results[product_id] = reserve_result
                        reserved_products.append(product_id)
                        
                    except Exception as e:
                        # Nếu có lỗi trong quá trình đặt trước, rollback các sản phẩm đã đặt trước
                        self._current_status = "FAILED"
                        workflow.logger.error(f"Failed to reserve inventory for product {product_id} in order {order_id}: {e}")
                        await self._rollback_reservations(reserved_products, order_id)
                        return {
                            "order_id": order_id,
                            "status": "FAILED",
                            "reason": f"Failed to reserve product {product_id}: {str(e)}",
                            "details": self._reservation_results
                        }
                
                # 3. Đợi tín hiệu commit hoặc rollback (hoặc hủy)
                try:
                    # Thiết lập timeout để không đợi mãi mãi
                    reservation_timeout = timedelta(hours=1)
                    try:
                        await asyncio.wait_for(
                            workflow.wait_condition(lambda: self._is_committed or self._is_cancelled),
                            timeout=reservation_timeout.total_seconds()
                        )
                    except asyncio.TimeoutError:
                        workflow.logger.warning(f"Reservation timeout for order {order_id}")
                        # Khi hết hạn, tự động rollback
                        self._is_cancelled = True
                
                except Exception as e:
                    workflow.logger.error(f"Error while waiting for commit/cancel signal: {e}")
                    self._is_cancelled = True
                
                # 4. Thực hiện commit hoặc rollback
                if self._is_committed:
                    # Commit: Cập nhật kho (giảm số lượng thực tế)
                    update_results = {}
                    for update in self._inventory_updates:
                        product_id = update["product_id"]
                        try:
                            result = await workflow.start_activity(
                                update_inventory,
                                args=[update],  # Pass arguments as a list
                                start_to_close_timeout=timedelta(seconds=15),
                            )
                            update_results[product_id] = result
                        except Exception as e:
                            workflow.logger.error(f"Failed to update inventory for product {product_id} in order {order_id}: {e}")
                            # Tiếp tục với sản phẩm tiếp theo, không rollback vì chúng ta đã cam kết
                    
                    self._current_status = "COMPLETED"
                    workflow.logger.info(f"Inventory successfully committed for order {order_id}")
                    return {
                        "order_id": order_id,
                        "status": "COMPLETED",
                        "details": update_results
                    }
                
                else:  # is_cancelled
                    # Rollback: Hủy đặt trước
                    await self._rollback_reservations(reserved_products, order_id)
                    
                    self._current_status = "CANCELLED"
                    workflow.logger.info(f"Inventory reservation cancelled for order {order_id}")
                    return {
                        "order_id": order_id,
                        "status": "CANCELLED",
                        "details": self._reservation_results
                    }
            
            except CancelledError:
                self._current_status = "CANCELLED"
                workflow.logger.info(f"Inventory workflow cancelled for order {order_id}")
                # Rollback khi workflow bị hủy
                await self._rollback_reservations(reserved_products, order_id)
                raise
        
        except Exception as e:
            # Bắt các lỗi không mong đợi
            self._current_status = "FAILED"
            workflow.logger.exception(f"Unhandled error in inventory workflow for order {order_id}: {e}")
            raise
        
        workflow.logger.info(f"Inventory workflow completed for order {order_id}")
        return {
            "order_id": order_id,
            "status": "COMPLETED" if self._is_committed else "CANCELLED",
            "details": self._reservation_results
        }

    async def _rollback_reservations(self, product_ids: List[str], order_id: str):
        """Hủy tất cả đặt trước đã thực hiện"""
        rollback_results = {}
        for product_id in product_ids:
            # Tìm update tương ứng
            update = next((u for u in self._inventory_updates if u["product_id"] == product_id), None)
            if update:
                try:
                    result = await workflow.start_activity(
                        unreserve_inventory,
                        args=[update],  # Pass arguments as a list
                        start_to_close_timeout=timedelta(seconds=10),
                    )
                    rollback_results[product_id] = result
                except Exception as e:
                    workflow.logger.error(f"Failed to unreserve product {product_id} for order {order_id}: {e}")
        
        return rollback_results

    @workflow.signal
    async def commit(self):
        """Tín hiệu xác nhận thực hiện cập nhật kho"""
        workflow.logger.info("Received commit signal")
        self._is_committed = True

    @workflow.signal
    async def cancel(self):
        """Tín hiệu hủy đặt trước, rollback"""
        workflow.logger.info("Received cancel signal")
        self._is_cancelled = True

    @workflow.query
    def get_status(self) -> str:
        """Trả về trạng thái hiện tại của workflow"""
        return self._current_status

    @workflow.query
    def get_reservation_details(self) -> dict:
        """Trả về chi tiết đặt trước kho hàng"""
        return self._reservation_results 