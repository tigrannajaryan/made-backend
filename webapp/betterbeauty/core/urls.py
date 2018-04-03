from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('djangoadmin/', admin.site.urls),
]
