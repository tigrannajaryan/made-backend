import logging
import os

import dj_database_url
import requests

logger = logging.getLogger(__name__)

# more details at https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-metadata.html
AWS_EC2_METADATA_URL = 'http://169.254.169.254/latest/meta-data'


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


def get_file_handler_dict(local_path: str, filename: str, formatter: str) -> dict:
    level = os.environ.get('LEVEL', '')
    # disable file logging on staging/production. It's useless in multi-instance
    # environment and produces all kinds of issues with log file permissions
    if level in ['staging', 'production']:
        return {
            'class': 'logging.NullHandler'
        }

    log_file_name = '{0}/{1}.log'.format(
        local_path, filename
    )
    return {
        'filename': log_file_name,
        'filters': ['require_debug_true', ],
        'formatter': formatter,
        'level': 'DEBUG',
        'class': 'logging.FileHandler'
    }


def get_logger_dict(handlers, level='INFO'):
    return {
        'handlers': handlers,
        'level': level,
        'propagate': False,
    }


def get_ec2_instance_ip():
    """Return IP address of current EC2 instance by requesting AWS metadata"""
    aws_get_ip_url = '{0}/local-ipv4'.format(AWS_EC2_METADATA_URL)
    try:
        aws_metadata = requests.get(aws_get_ip_url, timeout=0.1)
        return aws_metadata.text
    except (ConnectionError, IOError):
        logger.exception(
            'Could not retrieve instance IP; instance will not pass the health check'
        )
    return None
