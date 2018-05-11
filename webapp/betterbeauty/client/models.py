from uuid import uuid4

from django.db import models

from core.models import User


class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)

    class Meta:
        db_table = 'client'

    def __str__(self):
        return self.user.get_full_name()
