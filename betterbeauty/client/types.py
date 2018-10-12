from model_utils import Choices

from core.types import StrEnum


class ClientPrivacy(StrEnum):
    PRIVATE = 'private'
    PUBLIC = 'public'


CLIENT_PRIVACY_CHOICES = Choices(
    (ClientPrivacy.PRIVATE.value, 'private', 'Private', ),
    (ClientPrivacy.PUBLIC.value, 'public', 'Public'),
)
