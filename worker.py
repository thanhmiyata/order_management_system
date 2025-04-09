import asyncio
import os
from dotenv import load_dotenv # Khôi phục import gốc
# from python_dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

# Import workflows and activities
# from workflows.order_workflow import OrderWorkflow # Import cũ
from workflows.order_workflow import OrderApprovalWorkflow # Import workflow mới
# To use the actual activities, uncomment the following lines and ensure
# the activity stubs in the workflow file are also correctly set up.
from activities.order_activities import all_activities

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

        # Create a worker that hosts both workflow and activity functions
        worker = Worker(
            client,
            task_queue=task_queue_name,
            # workflows=[OrderWorkflow], # Đăng ký workflow cũ
            workflows=[OrderApprovalWorkflow], # Đăng ký workflow mới
            activities=all_activities, # Use real activities when ready
            # activities=mock_activities, # Use mock activities for now
            # You might want to adjust concurrent activity/workflow limits
            # max_concurrent_activities=100,
            # max_concurrent_workflow_tasks=100,
        )
        print(f"Starting worker on task queue '{task_queue_name}'...")
        await worker.run()
        print("Worker stopped.")

    except Exception as e:
        print(f"Error connecting to Temporal or running worker: {e}")
        # Consider adding retry logic or specific error handling here

if __name__ == "__main__":
    asyncio.run(main())
