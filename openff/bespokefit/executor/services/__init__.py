from openff.bespokefit.executor.services._settings import Settings


def current_settings() -> Settings:
    return Settings()


__all__ = ["current_settings", "Settings"]
