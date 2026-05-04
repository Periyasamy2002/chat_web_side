from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_category', 'mobile_number', 'is_approved')
    list_filter = ('is_approved',)
    actions = ['approve_users']

    def user_category(self, obj):
        return "Admin" if obj.user.is_superuser else "User"
    user_category.short_description = 'User Category'

    def approve_users(self, request, queryset):
        queryset.update(is_approved=True)
