"""Backend service for metadata management"""

from .core.config import settings
from .core.database import init_database
from .api.app import create_app

__version__ = "0.1.0" 