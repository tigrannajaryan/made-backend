from custom_user.admin import EmailUserAdmin

from django.contrib import admin

from core.models import User


class RoleListFilter(admin.SimpleListFilter):
    """This is a list filter based on the values
    from a model's `keywords` ArrayField. """

    title = 'Roles'
    parameter_name = 'roles'

    def lookups(self, request, model_admin):
        # Very similar to our code above, but this method must return a
        # list of tuples: (lookup_value, human-readable value). These
        # appear in the admin's right sidebar

        roles = User.objects.values_list("role", flat=True)
        roles = [(kw, kw) for sublist in roles for kw in sublist if kw]
        roles = sorted(set(roles))
        return roles

    def queryset(self, request, queryset):
        # when a user clicks on a filter, this method gets called. The
        # provided queryset with be a queryset of Items, so we need to
        # filter that based on the clicked keyword.

        lookup_value = self.value()  # The clicked keyword. It can be None!
        if lookup_value:
            # the __contains lookup expects a list, so...
            queryset = queryset.filter(role__contains=[lookup_value])
        return queryset

class UserAdmin(EmailUserAdmin):
    list_display = ('__str__', 'email', 'role', 'is_superuser', 'date_joined',
                    'is_active',)
    list_filter = (RoleListFilter, 'is_staff', 'is_superuser', 'is_active', )
    search_fields = ('email', 'first_name', 'last_name', 'phone', )

    fieldsets = (
        (None, {'fields': (
            'email', 'password', 'first_name', 'last_name', 'phone', 'photo'
        )}),
        ('Permissions', {'fields': ('is_active', 'role', 'is_staff', 'is_superuser')})
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'password1', 'password2', 'first_name', 'last_name', 'phone', 'photo'
            )
        }),
        ('Permissions', {'fields': ('role', 'is_staff', 'is_active', 'is_superuser',)})
    )


admin.site.register(User, UserAdmin)
