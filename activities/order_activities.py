from temporalio import activity
from temporalio.exceptions import ApplicationError # Import ApplicationError
from datetime import timedelta
import time # For simulating work
import random
import sys
import os
import asyncio # Import asyncio

# Adjust the import path based on your project structure
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.order import Order # Import necessary models

# Placeholder database/service interactions
# Replace these with actual interactions with Postgres, Redis, payment gateways, shipping APIs, etc.

async def _simulate_external_call(operation: str, order_id: str, duration_seconds: int = 1):
    activity.logger.info(f"Performing '{operation}' for order {order_id}...")
    # await activity.sleep(duration_seconds) # Simulate network delay/processing time
    await asyncio.sleep(duration_seconds) # Use asyncio.sleep instead
    # Simulate potential failures
    # if random.random() < 0.1: # 10% chance of failure
    activity.logger.info(f"'{operation}' for order {order_id} completed.")


@activity.defn
async def validate_order(order_data: dict) -> bool:
    order_id = order_data.get("id")
    total_amount = order_data.get("total_amount", 0)
    activity.logger.info(f"Validating order {order_id} with amount ${total_amount:.2f}")

    # Simulate invalid data check (non-retryable error)
    if total_amount < 0:
        activity.logger.error(f"Validation failed for order {order_id}: Invalid total amount.")
        # Raise ApplicationError for non-retryable business logic failures
        raise ApplicationError(f"Invalid order total: ${total_amount:.2f}", non_retryable=True)

    # Simulate temporary failures (retryable)
    failure_chance = 0.6 # 60% chance to fail temporarily
    if random.random() < failure_chance:
        activity.logger.warning(f"Simulating temporary validation failure for order {order_id}")
        await asyncio.sleep(1) # Simulate delay during failure
        raise ValueError("Temporary validation service unavailable")

    # Simulate validation time
    await asyncio.sleep(2)

    activity.logger.info(f"Order {order_id} validated successfully.")
    return True

@activity.defn
async def notify_manager(order_id: str):
    activity.logger.info(f"Notifying manager about pending approval for order {order_id}")
    await asyncio.sleep(0.5) # Simulate notification time
    # TODO: Implement actual notification (email, Slack, etc.)
    activity.logger.info(f"Manager notification sent for order {order_id}")

@activity.defn
async def process_approved_order(order_id: str):
    activity.logger.info(f"Processing approved order {order_id} (e.g., initiate payment/shipping)")
    await asyncio.sleep(2) # Simulate processing time
    # TODO: Call other activities like process_payment, ship_order etc.
    activity.logger.info(f"Approved order {order_id} processed.")

@activity.defn
async def notify_rejection(order_id: str):
    activity.logger.info(f"Notifying customer about rejected order {order_id}")
    await asyncio.sleep(0.5) # Simulate notification time
    # TODO: Implement actual notification
    activity.logger.info(f"Rejection notification sent for order {order_id}")

@activity.defn
async def handle_cancellation(order_id: str):
    activity.logger.info(f"Handling cancellation for order {order_id}")
    # TODO: Implement cancellation logic (e.g., notify warehouse, process refund if applicable)
    # Check current state before acting (e.g., was payment processed? was it shipped?)
    await _simulate_external_call("cancellation handling", order_id, duration_seconds=1)
    activity.logger.info(f"Cancellation processed for order {order_id}")

@activity.defn
async def cleanup_order(order_id: str):
    activity.logger.warning(f"Running cleanup for failed order {order_id}")
    # TODO: Implement cleanup logic for failed workflows
    await _simulate_external_call("failure cleanup", order_id, duration_seconds=1)
    activity.logger.info(f"Cleanup complete for order {order_id}")

# Gather all activities for the new workflow
all_activities = [
    validate_order,
    notify_manager,
    process_approved_order,
    notify_rejection,
    # Include old activities if still needed, e.g., for compensation or different flows
    handle_cancellation, # Keep for potential cancellation logic
    cleanup_order,       # Keep for potential general failure cleanup
]
