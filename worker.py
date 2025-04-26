import asyncio
import os
from dotenv import load_dotenv # Khôi phục import gốc
# from python_dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker
import logging
from temporalio import workflow

# Import workflows
from workflows.order_workflow import OrderApprovalWorkflow  
from workflows.payment_workflow import PaymentWorkflow  
from workflows.inventory_workflow import InventoryWorkflow

# Import activities
from activities.order_activities import all_activities as order_activities
from activities.payment_activities import payment_activities
from activities.inventory_activities import inventory_activities

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    load_dotenv() # Load .env file
    host = os.getenv("TEMPORAL_HOST", "localhost")
    port = os.getenv("TEMPORAL_PORT", "7233")
    
    # Use default namespace for all workflows
    namespace = "default"
    
    order_task_queue = "order-task-queue"
    payment_task_queue = "payment-task-queue"
    inventory_task_queue = "inventory-task-queue"

    logger.info(f"Connecting to Temporal at {host}:{port}...")
    try:
        # Create client with default namespace
        logger.info(f"Connecting to namespace: {namespace}")
        client = await Client.connect(f"{host}:{port}", namespace=namespace)
        logger.info(f"Successfully connected to namespace: {namespace}")

        # Create workers for different task queues with their specific activities
        logger.info(f"\nCreating order worker for task queue: {order_task_queue}")
        order_worker = Worker(
            client,
            task_queue=order_task_queue,
            workflows=[OrderApprovalWorkflow],
            activities=order_activities,
            max_concurrent_activities=50,
        )
        logger.info(f"Order worker created with {len(order_activities)} activities")

        logger.info(f"\nCreating payment worker for task queue: {payment_task_queue}")
        payment_worker = Worker(
            client,
            task_queue=payment_task_queue,
            workflows=[PaymentWorkflow],
            activities=payment_activities,
            max_concurrent_activities=50
        )
        logger.info(f"Payment worker created with {len(payment_activities)} activities")

        logger.info(f"\nCreating inventory worker for task queue: {inventory_task_queue}")
        inventory_worker = Worker(
            client,
            task_queue=inventory_task_queue,
            workflows=[InventoryWorkflow],
            activities=inventory_activities,
            max_concurrent_activities=50,
        )
        logger.info(f"Inventory worker created with {len(inventory_activities)} activities")

        logger.info("\nStarting all workers... Press Ctrl+C to exit")
        try:
            await asyncio.gather(
                order_worker.run(),
                payment_worker.run(),
                inventory_worker.run()
            )
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Error in worker: {e}")
        raise

if __name__ == "__main__":
    # Sử dụng new_event_loop thay vì run để có thể quản lý event loop tốt hơn
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        loop.close()
        logger.info("Worker shutdown complete")
