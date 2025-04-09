from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, CancelledError # Import exceptions
from datetime import timedelta
import sys
import os
import asyncio

# Adjust the import path based on your project structure
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.order import Order, OrderStatus # Import necessary models
# Placeholder for activities import
# from activities.order_activities import OrderActivities

# Define activities stub with retry policy
# This requires OrderActivities to be defined with @activity.defn
# Replace "OrderActivities" with the actual class name if different
with workflow.unsafe.imports_passed_through():
    # Import the activity functions we defined (currently mocks in worker.py)
    # In a real scenario, you'd import the interface or a generated stub
    from activities.order_activities import (
        validate_order,
        notify_manager,
        process_approved_order,
        notify_rejection,
        handle_cancellation,
        cleanup_order
    )

@workflow.defn(name="OrderApprovalWorkflow") # Changed name for clarity
class OrderApprovalWorkflow:
    def __init__(self):
        self._order_state: Order | None = None
        self._is_cancelled: bool = False
        self._approval_decision: str | None = None # To store approval signal result
        # Define RetryPolicy specifically for validation
        self._validation_retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=2),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
            # Do not retry ApplicationError (e.g., invalid data)
            non_retryable_error_types=["ApplicationError"],
        )
        # Define activity options (timeouts are now set per-activity call)
        # self._activity_options = {
        #     "start_to_close_timeout": timedelta(seconds=60),
        #     "retry_policy": self._activity_retry_policy,
        # }
        # Remove activity stub creation
        # self._activities = workflow.new_activity_stub(...)

    @workflow.run
    async def run(self, order_input: dict):
        self._order_state = Order(**order_input)
        workflow.logger.info(f"Starting OrderApprovalWorkflow for order: {self._order_state.id}")
        self._order_state.status = OrderStatus.CREATED

        try:
            # 1. Validate Order (Activity with Retry)
            self._update_status(OrderStatus.VALIDATION_PENDING)
            try:
                await workflow.start_activity(
                    validate_order,
                    self._order_state.model_dump(),
                    retry_policy=self._validation_retry_policy,
                    start_to_close_timeout=timedelta(minutes=1),
                )
                # Validation successful
                workflow.logger.info(f"Order {self._order_state.id} passed validation.")

            except ApplicationError as e:
                # Non-retryable validation failure (e.g., bad data)
                workflow.logger.error(f"Order {self._order_state.id} validation failed permanently: {e}")
                self._update_status(OrderStatus.VALIDATION_FAILED)
                return self._order_state.model_dump()

            except ActivityError as e:
                # Failure after all retries for retryable errors
                workflow.logger.error(f"Order {self._order_state.id} validation failed after retries: {e}")
                self._update_status(OrderStatus.AUTO_REJECTED)
                 # Optionally run cleanup/notification for auto-rejection
                return self._order_state.model_dump()

            except CancelledError:
                 workflow.logger.info(f"Workflow cancelled during order validation for {self._order_state.id}.")
                 self._update_status(OrderStatus.CANCELLED)
                 # Signal handler should have set _is_cancelled
                 raise # Re-raise to ensure workflow shows as cancelled

            # Check for cancellation signal received during validation activity
            if self._is_cancelled:
                workflow.logger.info(f"Handling cancellation after validation for {self._order_state.id}.")
                await self._handle_cancellation_logic()
                return self._order_state.model_dump()

            # 2. Pending Approval & Wait for Signal
            self._update_status(OrderStatus.PENDING_APPROVAL)
            await workflow.start_activity(
                notify_manager,
                self._order_state.id,
                start_to_close_timeout=timedelta(seconds=30),
             )

            workflow.logger.info(f"Order {self._order_state.id} waiting for approval signal.")
            try:
                # Wait indefinitely (or add a timeout) for the decision signal
                await workflow.wait_condition(lambda: self._approval_decision is not None)
            except CancelledError:
                workflow.logger.info(f"Workflow cancelled while waiting for approval for {self._order_state.id}.")
                self._update_status(OrderStatus.CANCELLED)
                await self._handle_cancellation_logic()
                raise

            # Check cancellation signal received while waiting
            if self._is_cancelled:
                 workflow.logger.info(f"Handling cancellation after wait_condition for {self._order_state.id}.")
                 await self._handle_cancellation_logic()
                 return self._order_state.model_dump()

            # 3. Process Decision
            workflow.logger.info(f"Received decision '{self._approval_decision}' for order {self._order_state.id}.")
            if self._approval_decision == "approved":
                self._update_status(OrderStatus.APPROVED)
                await workflow.start_activity(
                    process_approved_order,
                    self._order_state.id,
                    start_to_close_timeout=timedelta(minutes=5), # Longer timeout for processing
                )
            elif self._approval_decision == "rejected":
                self._update_status(OrderStatus.REJECTED)
                await workflow.start_activity(
                    notify_rejection,
                    self._order_state.id,
                    start_to_close_timeout=timedelta(seconds=30),
                )
            else:
                # Should not happen with current signal logic, but good to handle
                workflow.logger.warning(f"Unknown approval decision '{self._approval_decision}' for order {self._order_state.id}.")
                # Decide how to handle - maybe mark as failed or requires manual intervention
                self._update_status(OrderStatus.VALIDATION_FAILED) # Reusing a failed state

        except Exception as e:
            # Catch any other unexpected errors during workflow execution
            workflow.logger.exception(f"Unhandled error in workflow for order {self._order_state.id}: {e}")
            if not self._is_cancelled:
                 # Mark as failed only if not already cancelled
                 self._update_status(OrderStatus.VALIDATION_FAILED) # Or a generic WORKFLOW_FAILED
            # Consider running a generic cleanup activity here
            raise # Re-raise for Temporal to record the failure properly

        finally:
            # This block executes whether the workflow succeeds, fails, or is cancelled
            workflow.logger.info(f"Workflow finished for order {self._order_state.id} with final status {self._order_state.status}")
            # Cleanup specific to cancellation might be handled within the cancellation checks/handler
            # if self._is_cancelled:
            #      await self._handle_cancellation_logic()

        return self._order_state.model_dump()

    def _update_status(self, new_status: OrderStatus):
        if self._order_state:
             workflow.logger.info(f"Updating order {self._order_state.id} status from {self._order_state.status} to {new_status}")
             self._order_state.status = new_status
             # TODO: Consider emitting events or persisting state changes if needed outside workflow state

    async def _handle_cancellation_logic(self):
        """Runs cleanup activity specific to cancellation."""
        if self._order_state:
            workflow.logger.info(f"Running cancellation handling activity for order {self._order_state.id}")
            await workflow.start_activity(
                handle_cancellation,
                self._order_state.id,
                start_to_close_timeout=timedelta(seconds=60),
                # Might not need retry policy for cleanup, or a different one
            )

    @workflow.query
    def get_status(self) -> str:
        """Returns the current status of the order."""
        if not self._order_state:
            return "UNKNOWN"
        return self._order_state.status.value

    @workflow.query
    def get_details(self) -> dict | None:
        """Returns the full order state."""
        if not self._order_state:
             return None
        return self._order_state.model_dump()

    @workflow.signal
    async def provide_decision(self, decision: str):
        """Signal to provide the approval/rejection decision."""
        decision = decision.lower()
        if decision in ["approved", "rejected"]:
            if self._approval_decision is None:
                workflow.logger.info(f"Received decision signal: '{decision}' for order {self._order_state.id if self._order_state else 'N/A'}")
                self._approval_decision = decision
            else:
                workflow.logger.warning(f"Decision signal '{decision}' already received for order {self._order_state.id if self._order_state else 'N/A'}. Ignoring.")
        else:
            workflow.logger.warning(f"Ignoring invalid decision signal: '{decision}'")

    @workflow.signal
    async def cancel_order(self):
        """Signal handler to request cancellation."""
        # Only allow cancellation before a final decision or state
        if self._order_state and self._order_state.status not in [
            OrderStatus.APPROVED,
            OrderStatus.REJECTED,
            OrderStatus.VALIDATION_FAILED,
            OrderStatus.AUTO_REJECTED,
            OrderStatus.CANCELLED,
            # Consider if PENDING_APPROVAL should be cancellable here or handled by wait_condition
        ]:
            if not self._is_cancelled:
                 workflow.logger.info(f"Received cancellation signal for order {self._order_state.id}")
                 self._is_cancelled = True
                 # The main workflow logic will check _is_cancelled at await points
                 # or explicitly call _handle_cancellation_logic
                 # We might set status to CANCELLED immediately or let the main flow handle it.
                 # Setting it here can be simpler if cancellation is immediate.
                 self._update_status(OrderStatus.CANCELLED)
            else:
                workflow.logger.info(f"Cancellation signal already received for order {self._order_state.id}")
        elif self._order_state:
             workflow.logger.warning(f"Cancellation rejected for order {self._order_state.id} in status {self._order_state.status}")
        else:
            workflow.logger.warning("Cancellation signal received but order state is not initialized.")

# Placeholder for workflow interface (if needed for strong typing)
# @workflow.defn
# class OrderWorkflowInterface:
#     @workflow.run
#     async def run(self, order_input: dict):
#         raise NotImplementedError
#
#     @workflow.query
#     def get_status(self) -> str:
#         raise NotImplementedError
#
#     @workflow.query
#     def get_details(self) -> dict | None:
#         raise NotImplementedError
#
#     @workflow.signal
#     async def cancel_order(self):
#         raise NotImplementedError
