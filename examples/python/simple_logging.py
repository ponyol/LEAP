"""
Example Python file with various logging patterns.

This file is used to test the Python AST parser.
"""

import logging

# Standard logging module
logging.basicConfig(level=logging.INFO)


def get_user(user_id: int) -> dict | None:
    """
    Retrieve a user by ID.

    This function demonstrates simple logging patterns.
    """
    logging.info(f"Fetching user with ID: {user_id}")

    # Simulate database lookup
    if user_id < 0:
        logging.error(f"Invalid user ID: {user_id}")
        return None

    if user_id == 404:
        logging.warning("User not found in database")
        return None

    logging.debug(f"Successfully retrieved user {user_id}")
    return {"id": user_id, "name": "John Doe"}


class UserService:
    """Service for managing users."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_user(self, username: str, email: str) -> dict:
        """Create a new user."""
        self.logger.info(f"Creating new user: {username}")

        if not email:
            self.logger.error("Email is required")
            raise ValueError("Email is required")

        user = {"username": username, "email": email}
        self.logger.debug(f"User created successfully: {user}")

        return user

    def delete_user(self, user_id: int) -> bool:
        """Delete a user."""
        self.logger.warning(f"Deleting user {user_id}")

        try:
            # Simulate deletion
            if user_id == 0:
                raise Exception("Cannot delete admin user")

            self.logger.info(f"User {user_id} deleted successfully")
            return True

        except Exception as e:
            self.logger.exception(f"Failed to delete user {user_id}: {e}")
            return False


def main():
    """Main function."""
    logger = logging.getLogger("main")

    logger.info("Application starting")

    service = UserService()
    user = service.create_user("alice", "alice@example.com")

    logger.info("Application finished")


if __name__ == "__main__":
    main()
