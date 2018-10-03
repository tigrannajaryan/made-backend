import logging
import os

from typing import Optional

import dj_database_url
import requests
from path import Path

from core.constants import EnvLevel

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
    level = os.environ.get('LEVEL', EnvLevel.DEVELOPMENT)
    # disable file logging on staging/production. It's useless in multi-instance
    # environment and produces all kinds of issues with log file permissions
    if level in [EnvLevel.STAGING, EnvLevel.PRODUCTION]:
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


def get_ec2_instance_ip_address() -> Optional[str]:
    """Return IP address of current EC2 instance by requesting AWS metadata"""
    aws_get_ip_url = '{0}/local-ipv4'.format(AWS_EC2_METADATA_URL)
    try:
        aws_metadata = requests.get(aws_get_ip_url, timeout=0.1)
        return aws_metadata.text
    except (ConnectionError, IOError):
        logger.exception(
            'Could not retrieve instance IP addr; instance will not pass the health check'
        )
    return None


def get_ec2_instance_id() -> Optional[str]:
    """Return AWS id of current EC2 instance by requesting AWS metadata"""
    aws_get_id_url = '{0}/instance-id'.format(AWS_EC2_METADATA_URL)
    try:
        aws_metadata = requests.get(aws_get_id_url, timeout=0.1)
        return aws_metadata.text
    except (ConnectionError, IOError):
        logger.exception(
            'Could not retrieve instance ID'
        )
    return None


def get_travis_commit_id(path_to_commit_id_file: Path) -> str:
    level = os.environ.get('LEVEL', EnvLevel.DEVELOPMENT)
    if level not in [EnvLevel.STAGING, EnvLevel.PRODUCTION]:
        return ''
    try:
        with open(path_to_commit_id_file, 'r') as commit_file:
            commit_id: str = commit_file.read()
            if commit_id:
                commit_id = commit_id.strip()
            return commit_id
    except FileNotFoundError:
        print('Could not read {0} file; no release msg will be added to Sentry messages'.format(
            path_to_commit_id_file
        ))
        logger.warning(
            'Could not read {0} file; no release msg will be added to Sentry messages'.format(
                path_to_commit_id_file
            ))
        return ''
