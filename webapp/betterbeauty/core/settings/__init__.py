import importlib
import logging
import os

logger = logging.getLogger(__name__)

level = os.environ.get('LEVEL', 'development')

globals().update(
    importlib.import_module('core.settings.{0}'.format(level)).__dict__
)

try:
    globals().update(
        importlib.import_module('core.settings.local').__dict__
    )
except ImportError:
    logger.warn('Could not import local settings module (local.py is missing)')
