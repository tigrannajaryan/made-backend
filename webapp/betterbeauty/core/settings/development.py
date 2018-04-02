from .defaults import *  # noqa
from .utils import parse_database_url

DATABASE_URL = (
    'postgres://betterbeauty:W8zSrpqUkFzReUqT@127.0.0.1:5432/betterbeauty'
)

# Setup default database connection from Database URL
DATABASES = {
    'default': parse_database_url(DATABASE_URL),
}

DEBUG = True
