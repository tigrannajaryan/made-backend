from model_utils import Choices

from .types import InvitationStatus

INVITATION_STATUS_CHOICES = Choices(
    (InvitationStatus.UNSENT.value, 'unsent', 'Not Sent Yet'),
    (InvitationStatus.DELIVERED.value, 'delivered', 'Delivered'),
    (InvitationStatus.UNDELIVERED.value, 'undelivered', 'Undelivered'),
    (InvitationStatus.ACCEPTED.value, 'accepted', 'Accepted'),
)
