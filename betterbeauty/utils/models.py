from django.db import models
from django.utils import timezone


class IgnoreDeletedManager(models.Manager):
    def get_queryset(self, *args, **kwargs):
        return super(IgnoreDeletedManager, self).get_queryset(*args, **kwargs).filter(
            deleted_at__isnull=True
        )


class IncludeDeletedManager(models.Manager):
    use_in_migrations = True


class SmartModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True, default=None)

    objects = IgnoreDeletedManager()
    all_objects = IncludeDeletedManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        if not self.deleted_at:
            self.deleted_at = timezone.now()
            self.save(update_fields=['deleted_at'])
        else:
            raise self.DoesNotExist

    def hard_delete(self, using=None, keep_parents=False):
        return super(SmartModel, self).delete(using, keep_parents)

    def safe_hard_delete(self, using=None, keep_parents=False):
        # hard_deletes only if it is already soft deleted
        if self.deleted_at:
            return self.hard_delete(using, keep_parents)
        else:
            return None
