from mimetypes import guess_extension
from uuid import uuid4

import requests


from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import ImageField


def fetch_image_to_image_field(image_url: str, target_field: ImageField) -> None:
    """Fetches image from url and assigns it to image file field"""
    response = requests.get(image_url)
    response.raise_for_status()

    content = response.content
    content_file = ContentFile(content)

    content_type = response.headers.get('content-type')
    extension = guess_extension(content_type)

    target_file_name = '{0}{1}'.format(uuid4(), extension)
    target_field.save(
        default_storage.get_available_name(target_file_name), content_file
    )
