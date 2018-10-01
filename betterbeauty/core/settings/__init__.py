import importlib
import logging
import os

from core.constants import EnvLevel

logger = logging.getLogger(__name__)

level = os.environ.get('LEVEL', EnvLevel.DEVELOPMENT)

globals().update(
    importlib.import_module('core.settings.{0}'.format(level)).__dict__
)

try:
    globals().update(
        importlib.import_module('core.settings.local').__dict__
    )
except ImportError:
    logger.warn('Could not import local settings module (local.py is missing)')
