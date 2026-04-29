from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("", views.home, name="home"),
    path("chat/", views.chat, name="chat"),
    path("group/<str:code>/", views.group, name="group"),
    path("group/<str:code>/upload-voice/", views.upload_voice_message, name="upload_voice"),
    path("group/<str:code>/synthesize-voice/", views.synthesize_voice_message, name="synthesize_voice"),
    path("group/<str:code>/delete-message/", views.delete_message, name="delete_message"),
    path("group/<str:code>/update-status/", views.update_user_status, name="update_status"),
    path("group/<str:code>/online-users/", views.get_online_users, name="get_online_users"),
    path("group/<str:code>/get-messages/", views.get_new_messages, name="get_messages"),
    path("group/<str:code>/send-message/", views.send_message_ajax, name="send_message_ajax"),
    path("group/<str:code>/translate/", views.translate_message, name="translate_message"),
    # Auto-deletion & cleanup monitoring
    path("group/<str:code>/cleanup-status/", views.get_group_cleanup_status, name="cleanup_status"),
    path("admin/groups-status/", views.get_all_groups_status, name="all_groups_status"),

    # Group Management and Creation
    path("group-manage/", views.group_manage, name="group_manage"),
    path("group-delete/<str:code>/", views.delete_group_entirely, name="delete_group_entirely"),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)