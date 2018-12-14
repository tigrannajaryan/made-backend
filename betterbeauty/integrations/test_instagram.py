# import requests
import mock
import pytest

from .instagram import (
    get_recent_media,
    InstagramContentType,
    InstagramImageResolutionType,
)


@pytest.fixture
def instagram_recent_media_response():
    return {
        "pagination": {},
        "data": [
            {
                "id": "1",
                "images": {
                    "thumbnail": {
                        "width": 150,
                        "height": 150,
                        "url": "https://th1.jpg"
                    },
                    "low_resolution": {
                        "width": 320,
                        "height": 320,
                        "url": "https://lr1.jpg"
                    },
                    "standard_resolution": {
                        "width": 640,
                        "height": 640,
                        "url": "https://sr1.jpg"
                    }
                },
                "likes": {
                    "count": 10
                },
                "type": "carousel",
            },
            {
                "id": "2",
                "images": {
                    "thumbnail": {
                        "width": 150,
                        "height": 150,
                        "url": "https://th2.jpg"
                    },
                    "low_resolution": {
                        "width": 320,
                        "height": 320,
                        "url": "https://lr2.jpg"
                    },
                    "standard_resolution": {
                        "width": 640,
                        "height": 640,
                        "url": "https://sr2.jpg"
                    }
                },
                "likes": {
                    "count": 20
                },
                "type": "video",
            },
            {
                "id": "3",
                "images": {
                    "thumbnail": {
                        "width": 150,
                        "height": 150,
                        "url": "https://th3.jpg"
                    },
                    "low_resolution": {
                        "width": 320,
                        "height": 180,
                        "url": "https://lr3.jpg"
                    },
                    "standard_resolution": {
                        "width": 640,
                        "height": 360,
                        "url": "https://sr3.jpg"
                    }
                },
                "likes": {
                    "count": 30
                },
                "type": "image",
            }
        ],
        "meta": {
            "code": 200
        }
    }


def mocked_instagram_requests_get(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

    return MockResponse(instagram_recent_media_response(), 200)


@mock.patch('integrations.instagram.requests.get', side_effect=mocked_instagram_requests_get)
def test_get_recent_media(api_mock):
    media = get_recent_media('some_token')
    assert(len(media) == 3)
    assert(media[0].content_type == InstagramContentType.CAROUSEL)
    assert(
        media[0].images[InstagramImageResolutionType.THUMBNAIL].url == 'https://th1.jpg'
    )
    assert (
        media[0].images[InstagramImageResolutionType.LOW_RESOLUTION].url == 'https://lr1.jpg'
    )
    assert (
        media[0].images[InstagramImageResolutionType.STANDARD_RESOLUTION].url == 'https://sr1.jpg'
    )
    assert(media[0].likes == 10)
    assert(media[1].content_type == InstagramContentType.VIDEO)
    assert (
        media[1].images[InstagramImageResolutionType.THUMBNAIL].url == 'https://th2.jpg'
    )
    assert (
        media[1].images[InstagramImageResolutionType.LOW_RESOLUTION].url == 'https://lr2.jpg'
    )
    assert (
        media[1].images[InstagramImageResolutionType.STANDARD_RESOLUTION].url == 'https://sr2.jpg'
    )
    assert (media[1].likes == 20)
    assert(media[2].content_type == InstagramContentType.IMAGE)
    assert (
        media[2].images[InstagramImageResolutionType.THUMBNAIL].url == 'https://th3.jpg'
    )
    assert (
        media[2].images[InstagramImageResolutionType.LOW_RESOLUTION].url == 'https://lr3.jpg'
    )
    assert (
        media[2].images[InstagramImageResolutionType.STANDARD_RESOLUTION].url == 'https://sr3.jpg'
    )
    assert (media[2].likes == 30)
