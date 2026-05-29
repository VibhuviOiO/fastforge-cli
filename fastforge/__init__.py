"""FastForge — production-grade FastAPI project generator."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fastforge-cli")
except PackageNotFoundError:
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
