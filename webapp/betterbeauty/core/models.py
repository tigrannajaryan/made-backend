from typing import List

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS: List[str] = []

    def is_customer(self) -> bool:
        return hasattr(self, 'customer')

    def is_stylist(self) -> bool:
        return hasattr(self, 'stylist')
