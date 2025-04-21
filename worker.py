import asyncio
import os
from dotenv import load_dotenv # Khôi phục import gốc
# from python_dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

# Import workflows
from workflows.order_workflow import OrderApprovalWorkflow  
from workflows.payment_workflow import PaymentWorkflow  
from workflows.inventory_workflow import InventoryWorkflow

# Import activities
from activities.order_activities import all_activities as order_activities
from activities.payment_activities import payment_activities
from activities.inventory_activities import inventory_activities

# --- Temporary Mock Activities --- (Remove when using real activities)
# Comment out or remove the mock activities section when using the real ones
"""
from temporalio import activity
from datetime import timedelta
import random

# Define mock activities directly here for simplicity until real ones are implemented
@activity.defn
async def process_payment(order_data: dict) -> bool:
    activity.logger.info(f"[Mock] Processing payment for order {order_data.get('id')}...")
    await asyncio.sleep(1)
    activity.logger.info(f"[Mock] Payment successful.")
    return True

@activity.defn
async def process_order(order_id: str):
    activity.logger.info(f"[Mock] Processing order {order_id}...")
    await asyncio.sleep(1)
    activity.logger.info(f"[Mock] Order processed.")

@activity.defn
async def ship_order(order_id: str) -> dict:
    activity.logger.info(f"[Mock] Shipping order {order_id}...")
    await asyncio.sleep(1)
    tracking_id = f"TRK-MOCK-{random.randint(1000, 9999)}"
    activity.logger.info(f"[Mock] Order shipped with tracking {tracking_id}.")
    return {"tracking_id": tracking_id}

@activity.defn
async def handle_cancellation(order_id: str):
    activity.logger.info(f"[Mock] Handling cancellation for {order_id}...")
    await asyncio.sleep(0.5)
    activity.logger.info(f"[Mock] Cancellation handled.")

@activity.defn
async def cleanup_order(order_id: str):
    activity.logger.info(f"[Mock] Cleaning up order {order_id}...")
    await asyncio.sleep(0.5)
    activity.logger.info(f"[Mock] Cleanup complete.")

mock_activities = [
    process_payment,
    process_order,
    ship_order,
    handle_cancellation,
    cleanup_order,
]
"""
# --- End Temporary Mock Activities ---

async def main():
    load_dotenv() # Load .env file
    host = os.getenv("TEMPORAL_HOST", "localhost")
    port = os.getenv("TEMPORAL_PORT", "7233")
    task_queue_name = "order-task-queue"

    print(f"Connecting to Temporal at {host}:{port}...")
    try:
        client = await Client.connect(f"{host}:{port}")
        print("Successfully connected to Temporal.")

        # Tạo một danh sách tất cả các activities
        all_activities = []
        all_activities.extend(order_activities)
        all_activities.extend(payment_activities)
        all_activities.extend(inventory_activities)

        # In ra thông tin về activities và workflows để debug
        print(f"Registering {len(all_activities)} activities")
        print(f"Registering workflows: OrderApprovalWorkflow, PaymentWorkflow, InventoryWorkflow")

        # Create a worker that hosts both workflow and activity functions
        worker = Worker(
            client,
            task_queue=task_queue_name,
            workflows=[
                OrderApprovalWorkflow,  # Quy trình phê duyệt đơn hàng
                PaymentWorkflow,        # Quy trình thanh toán
                InventoryWorkflow       # Quy trình quản lý kho hàng
            ],
            activities=all_activities,  # Tất cả các activities
            # You might want to adjust concurrent activity/workflow limits
            # max_concurrent_activities=100,
            # max_concurrent_workflow_tasks=100,
        )
        print(f"Starting worker on task queue '{task_queue_name}'...")
        await worker.run()
        print("Worker stopped.")

    except Exception as e:
        print(f"Error connecting to Temporal or running worker: {e}")
        import traceback
        traceback.print_exc()  # In ra stack trace đầy đủ để debug

if __name__ == "__main__":
    asyncio.run(main())
