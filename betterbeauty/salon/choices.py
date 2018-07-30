from model_utils import Choices

from .types import InvitationStatus

INVITATION_STATUS_CHOICES = Choices(
    (InvitationStatus.INVITED.value, 'invited', 'Invited'),
    (InvitationStatus.ACCEPTED.value, 'accepted', 'Accepted'),
)
