from typing import Dict, Optional, Tuple

import facebook

from django.conf import settings
from django.db import transaction

from core.choices import USER_ROLE
from core.models import User
from core.types import FBAccessToken, FBUserID
from ..utils.storage import fetch_image_to_image_field

facebook_application_api = facebook.GraphAPI()


def verify_fb_token(fb_user_token: FBAccessToken, fb_user_id: FBUserID) -> bool:
    """Returns True if token is valid"""
    response = facebook_application_api.debug_access_token(
        fb_user_token, settings.FB_APP_ID, settings.FB_APP_SECRET
    )
    is_valid = response.get('data', {}).get('is_valid', False)

    if not is_valid:
        return False

    verified_user_id = response['data']['user_id']
    verified_app_id = response['data']['app_id']

    return verified_user_id == fb_user_id and verified_app_id == settings.FB_APP_ID


def get_profile_data(fb_user_token: FBAccessToken, fb_user_id: FBUserID) -> Dict:
    api = facebook.GraphAPI(access_token=fb_user_token)
    return api.get_object(
        fb_user_id, fields='email, first_name, last_name, picture'
    )


def get_or_create_facebook_user(
        fb_user_token: FBAccessToken, fb_user_id: FBUserID
) -> Tuple[User, bool]:
    profile_data: Dict = get_profile_data(fb_user_token, fb_user_id)
    first_name: str = profile_data.get('first_name', '')
    last_name: str = profile_data.get('last_name', '')
    picture_url: Optional[str] = profile_data.get(
        'picture', {}).get('data', {}).get('url', '')
    email = profile_data['email']

    with transaction.atomic():
        # get or create user based on the profile data
        user, created = User.objects.get_or_create(defaults={
            'first_name': first_name,
            'last_name': last_name,
        }, facebook_id=fb_user_id, role=USER_ROLE.stylist, email=email
        )
        if created and picture_url:
            # try to fetch and save profile picture
            fetch_image_to_image_field(picture_url, user.photo)

        return user, created
