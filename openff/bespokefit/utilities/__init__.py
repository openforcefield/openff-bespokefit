"""Tools, methods and types used throughout BespokeFit."""

from openff.bespokefit.utilities._settings import Settings


def current_settings() -> Settings:
    """Return default settings."""
    return Settings()


__all__ = ["current_settings", "Settings"]
