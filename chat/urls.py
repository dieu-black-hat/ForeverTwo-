from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    # Accounts
    path("login/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("account/password/", views.change_password, name="change_password"),
    path("people/manage/", views.manage_users, name="manage_users"),
    path("people/<int:user_id>/action/", views.user_action, name="user_action"),
    # Pages
    path("", views.home, name="home"),
    path("rooms/new/", views.create_room, name="create_room"),
    path("rooms/<slug:slug>/", views.room_view, name="room"),
    path("rooms/<slug:slug>/leave/", views.leave_room, name="leave_room"),
    path("dm/<str:username>/", views.direct_message, name="direct_message"),
    path("files/<int:message_id>/", views.message_file, name="message_file"),
    # JSON API used by app.js
    path("api/rooms/<slug:slug>/messages/", views.api_messages, name="api_messages"),
    path("api/rooms/<slug:slug>/send/", views.api_send, name="api_send"),
    path("api/rooms/<slug:slug>/upload/", views.api_upload, name="api_upload"),
    path("api/rooms/<slug:slug>/typing/", views.api_typing, name="api_typing"),
    path("api/rooms/<slug:slug>/screenshot/", views.api_screenshot, name="api_screenshot"),
    path("api/messages/<int:message_id>/delete/", views.api_delete, name="api_delete"),
    path("api/sidebar/", views.api_sidebar, name="api_sidebar"),
    # JSON API used by call.js
    path("api/calls/signal/", views.api_call_signal, name="api_call_signal"),
    path("api/calls/poll/", views.api_call_poll, name="api_call_poll"),
]
