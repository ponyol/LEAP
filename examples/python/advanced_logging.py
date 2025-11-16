"""
Advanced logging patterns for testing.

This file demonstrates more complex logging scenarios.
"""

import logging
from typing import Any

# Custom logger instance
logger = logging.getLogger(__name__)


def process_payment(amount: float, currency: str) -> bool:
    """
    Process a payment transaction.

    This demonstrates logging with multiple variables.
    """
    logger.info(f"Processing payment: {amount} {currency}")

    if amount <= 0:
        logger.error(f"Invalid payment amount: {amount}")
        return False

    if currency not in ["USD", "EUR", "GBP"]:
        logger.warning(f"Unsupported currency: {currency}, defaulting to USD")
        currency = "USD"

    # Simulate payment processing
    logger.debug(f"Sending payment request to processor")

    try:
        # Simulate API call
        success = True
        if success:
            logger.info(f"Payment of {amount} {currency} processed successfully")
        else:
            logger.error("Payment processing failed")

        return success

    except Exception as e:
        logger.critical(f"Critical error during payment processing: {e}")
        raise


class APIClient:
    """API client with structured logging."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self._logger = logging.getLogger(f"{__name__}.APIClient")

    def fetch_data(self, endpoint: str) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        url = f"{self.base_url}/{endpoint}"
        self._logger.info(f"Fetching data from {url}")

        try:
            # Simulate API call
            data = {"status": "success"}
            self._logger.debug(f"Received response: {data}")
            return data

        except ConnectionError as e:
            self._logger.error(f"Connection failed to {url}: {e}")
            raise

        except TimeoutError:
            self._logger.warning(f"Request to {url} timed out, retrying...")
            # Retry logic would go here
            return {}


def complex_operation():
    """Demonstrate nested logging scenarios."""
    log = logging.getLogger("operations")

    log.info("Starting complex operation")

    for i in range(3):
        log.debug(f"Processing item {i}")

        if i == 2:
            log.warning(f"Item {i} requires special handling")

    log.info("Complex operation completed")
