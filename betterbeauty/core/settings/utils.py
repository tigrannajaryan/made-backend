import os

import dj_database_url


def parse_database_url(database_url, ssl_cert=None):
    """Parse datbase URL and append proper test config to it."""
    options = {}
    if ssl_cert is not None:
        options = {
            'OPTIONS': {
                'sslmode': 'require',
                'sslrootcert': ssl_cert,
            },
        }

    return dict(dj_database_url.parse(database_url),
                TEST={'CHARSET': 'UTF8'},
                **options)


def get_handler_dict(local_path: str, filename: str, formatter: str) -> dict:
    level = os.environ.get('LEVEL', '')
    if level in ['staging', 'production']:
        log_path = '/var/log/madebeauty'
    else:
        log_path = local_path
    log_file_name = '{0}/{1}.log'.format(
        log_path, filename
    )
    return {
        'filename': log_file_name,
        'formatter': formatter,
        'level': 'DEBUG',
        'class': 'logging.FileHandler'
    }


def get_logger_dict(handlers, level='INFO'):
    return {
        'handlers': handlers,
        'level': level,
        'propagate': True,
    }
