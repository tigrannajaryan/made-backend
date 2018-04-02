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
