"""Logging utilities."""

import logging


class DeprecationWarningFilter(logging.Filter):
    """Handle deprecation warnings."""

    def filter(self, record):
        """Filter out deprecation warnings."""
        return "is deprecated" not in record.getMessage()
