from typing import Dict, List, NamedTuple, Optional

import requests
from rest_framework import status

from core.types import StrEnum

INSTAGRAM_API_ENDPOINT = 'https://api.instagram.com/v1'


class InstagramContentType(StrEnum):
    IMAGE = 'image'
    VIDEO = 'video'
    CAROUSEL = 'carousel'


class InstagramImageResolutionType(StrEnum):
    THUMBNAIL = 'thumbnail'
    LOW_RESOLUTION = 'low_resolution'
    STANDARD_RESOLUTION = 'standard_resolution'


class InstagramImageInfo(NamedTuple):
    url: str
    width: int
    height: int


class InstagramMediaItem(NamedTuple):
    id: str
    content_type: InstagramContentType
    images: Dict[InstagramImageResolutionType, InstagramImageInfo]
    likes: int


def get_recent_media(
        access_token: str,
        count: Optional[int]=None,
        min_id: Optional[str]=None,
        max_id: Optional[str]=None,
) -> List[InstagramMediaItem]:
    """
    Get the most recent media published by the owner of the access_token
    :param access_token: A valid access token
    :param count: Count of media to return
    :param min_id: Return media later than this min_id
    :param max_id: Return media earlier than this max_id
    :return: List of InstagramMediaItem objects
    """
    url = '{0}/users/self/media/recent/?access_token={1}'.format(
        INSTAGRAM_API_ENDPOINT, access_token
    )
    if count is not None:
        url = '{0}&count={1}'.format(url, count)
    if max_id is not None:
        url = '{0}&max_id={1}'.format(url, max_id)
    if min_id is not None:
        url = '{0}&min_id={1}'.format(url, min_id)

    response = requests.get(url)
    media_items: List[InstagramMediaItem] = []
    if status.is_success(response.status_code):
        for media_item in response.json()['data']:
            media_items.append(InstagramMediaItem(
                id=media_item['id'],
                images={
                    InstagramImageResolutionType(k): InstagramImageInfo(**v)
                    for k, v in media_item['images'].items()
                },
                content_type=InstagramContentType(media_item['type']),
                likes=int(media_item['likes']['count'])
            ))
    return media_items
