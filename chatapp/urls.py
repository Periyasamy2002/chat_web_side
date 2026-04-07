from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("chat/", views.chat, name="chat"),
    path("group/<str:code>/", views.group, name="group"),
    path("group/<str:code>/upload-voice/", views.upload_voice_message, name="upload_voice"),
    path("group/<str:code>/delete-message/", views.delete_message, name="delete_message"),
    path("group/<str:code>/update-status/", views.update_user_status, name="update_status"),
    path("group/<str:code>/online-users/", views.get_online_users, name="get_online_users"),
]