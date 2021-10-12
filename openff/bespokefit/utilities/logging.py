import logging


class DeprecationWarningFilter(logging.Filter):
    def filter(self, record):
        return "is deprecated" not in record.getMessage()
