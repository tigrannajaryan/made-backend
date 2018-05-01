from django.db import models

from core.models import User


class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    class Meta:
        db_table = 'client'

    def __str__(self):
        return self.user.get_full_name()
