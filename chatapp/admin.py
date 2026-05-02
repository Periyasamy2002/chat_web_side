from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'mobile_number', 'is_approved')
    list_filter = ('is_approved',)
    actions = ['approve_users']

    def approve_users(self, request, queryset):
        queryset.update(is_approved=True)
