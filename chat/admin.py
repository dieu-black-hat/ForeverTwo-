from django.contrib import admin

from .models import Message, Presence, Profile, Room


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_private", "is_direct", "created_by", "created_at")
    list_filter = ("is_private", "is_direct")
    search_fields = ("name", "slug")
    filter_horizontal = ("members",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("user", "room", "short_content", "created_at")
    list_filter = ("room",)
    search_fields = ("content", "user__username")

    @admin.display(description="Message")
    def short_content(self, obj):
        return obj.content[:60]


@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = ("user", "last_seen")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "must_change_password", "created_by")
