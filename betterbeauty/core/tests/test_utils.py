from core.utils.phone import to_international_format


def test_to_international_format():
    # with country defined - US
    assert(
        to_international_format('+16135551234', 'US') == '+1 613-555-1234')
    # without country defined
    assert(
        to_international_format('+16135551234', None) == '+1 613-555-1234'
    )
