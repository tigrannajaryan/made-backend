from enum import Enum


class InvitationStatus(str, Enum):
    UNSENT = 'unsent'
    DELIVERED = 'delivered'
    UNDELIVERED = 'undelivered'
    ACCEPTED = 'accepted'
