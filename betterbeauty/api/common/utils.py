from typing import Optional

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404

from core.models import TemporaryFile, User


def save_profile_photo(
        user: Optional[User], photo_uuid: Optional[str]
) -> None:
    if not user or not photo_uuid:
        return

    image_file_record: TemporaryFile = get_object_or_404(
        TemporaryFile,
        uuid=photo_uuid,
        uploaded_by=user
    )
    content_file = ContentFile(image_file_record.file.read())
    target_file_name = image_file_record.file.name
    user.photo.save(
        default_storage.get_available_name(target_file_name), content_file
    )
    image_file_record.file.close()
