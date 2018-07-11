from datetime import datetime

from django.db import models


class IgnoreDeletedManager(models.Manager):
    def get_queryset(self, *args, **kwargs):
        return super(IgnoreDeletedManager, self).get_queryset(*args, **kwargs).filter(
            deleted_at__isnull=True
        )


class IncludeDeletedManager(models.Manager):
    use_in_migrations = True


class SmartModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    objects = IgnoreDeletedManager()
    all_objects = IncludeDeletedManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        if not self.deleted_at:
            self.deleted_at = datetime.now()
            self.save(update_fields=['deleted_at'])
        else:
            raise self.DoesNotExist
