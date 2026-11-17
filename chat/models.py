"""
Database tables for the chat.

Room        – a conversation (public room, private room, or a 1-to-1 direct message)
Message     – one item in a room: text, photo, video, file, voice note or call record
ReadMarker  – the last message each user has read in each room (unread badges, "Seen")
Presence    – when each user was last active (green "online" dot)
Typing      – who is typing right now ("grace is typing…")
CallSignal  – short messages two browsers exchange to set up an audio/video call
Profile     – extra account info (e.g. "must change password at next login")
"""
import hashlib
import os
import uuid

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

AVATAR_COLORS = [
    "#e11d48", "#db2777", "#9333ea", "#4f46e5", "#2563eb", "#0891b2",
    "#0d9488", "#059669", "#65a30d", "#ca8a04", "#ea580c", "#dc2626",
]


def avatar_color(username):
    """Give every username a stable colour for its avatar circle."""
    digest = hashlib.md5(username.encode("utf-8")).hexdigest()
    return AVATAR_COLORS[int(digest, 16) % len(AVATAR_COLORS)]


class Room(models.Model):
    name = models.CharField(max_length=60)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.CharField(max_length=200, blank=True)
    is_private = models.BooleanField(default=False, help_text="Only invited members can see it.")
    is_direct = models.BooleanField(default=False, help_text="A 1-to-1 direct message.")
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="chat_rooms", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_rooms",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def can_access(self, user):
        if not self.is_private:
            return True
        return self.members.filter(pk=user.pk).exists()

    def other_member(self, user):
        """For a direct message, the person you are talking to."""
        for member in self.members.all():
            if member.pk != user.pk:
                return member
        return None

    def display_name_for(self, user):
        if self.is_direct:
            other = self.other_member(user)
            return other.username if other else "Just you"
        return self.name

    @staticmethod
    def make_unique_slug(name):
        base = slugify(name)[:60] or "room"
        slug, counter = base, 2
        while Room.objects.filter(slug=slug).exists():
            slug = f"{base}-{counter}"
            counter += 1
        return slug


def attachment_path(instance, filename):
    """Files are saved with a random name, e.g. media/chat/image/2026/11/3f2a….jpg"""
    ext = os.path.splitext(filename)[1].lower()[:10]
    return f"chat/{instance.kind}/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


class Message(models.Model):
    TEXT, IMAGE, VIDEO, FILE, VOICE, CALL = "text", "image", "video", "file", "voice", "call"
    KIND_CHOICES = [
        (TEXT, "Text"), (IMAGE, "Photo"), (VIDEO, "Video"),
        (FILE, "File"), (VOICE, "Voice note"), (CALL, "Call record"),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=TEXT)
    content = models.TextField(max_length=settings.CHAT_MAX_MESSAGE_LENGTH, blank=True)
    attachment = models.FileField(upload_to=attachment_path, blank=True, max_length=255)
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    mime = models.CharField(max_length=100, blank=True)
    duration = models.PositiveIntegerField(default=0, help_text="Seconds (voice notes)")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.user}: [{self.kind}] {self.content[:40]}"

    def soft_delete(self):
        """'Delete for everyone': remove the content and file but keep a placeholder."""
        if self.attachment:
            self.attachment.delete(save=False)
        self.content = ""
        self.file_name = ""
        self.deleted_at = timezone.now()
        self.save()

    def to_dict(self, viewer):
        """The shape the browser receives as JSON."""
        data = {
            "id": self.id,
            "user": self.user.username,
            "kind": self.kind,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "color": avatar_color(self.user.username),
            "is_mine": self.user_id == viewer.pk,
        }
        if self.deleted_at:
            data.update(kind="deleted", content="")
            return data
        if self.attachment:
            data.update(
                file_url=reverse("message_file", args=[self.id]),
                file_name=self.file_name,
                file_size=self.file_size,
                mime=self.mime,
                duration=self.duration,
            )
        return data


@receiver(post_delete, sender=Message)
def _remove_file(sender, instance, **kwargs):
    if instance.attachment:
        instance.attachment.delete(save=False)


class ReadMarker(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    last_read_id = models.PositiveBigIntegerField(default=0)

    class Meta:
        unique_together = ("user", "room")

    @classmethod
    def mark(cls, user, room, message_id):
        marker, _ = cls.objects.get_or_create(user=user, room=room)
        if message_id > marker.last_read_id:
            marker.last_read_id = message_id
            marker.save(update_fields=["last_read_id"])


class Presence(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    last_seen = models.DateTimeField(default=timezone.now)

    @classmethod
    def touch(cls, user):
        """Record that the user is active (writes at most every 20 seconds)."""
        now = timezone.now()
        presence, created = cls.objects.get_or_create(user=user)
        if not created and (now - presence.last_seen).total_seconds() > 20:
            presence.last_seen = now
            presence.save(update_fields=["last_seen"])

    @classmethod
    def online_user_ids(cls):
        cutoff = timezone.now() - timezone.timedelta(seconds=settings.CHAT_ONLINE_SECONDS)
        return set(cls.objects.filter(last_seen__gte=cutoff).values_list("user_id", flat=True))


class Typing(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "room")


class CallSignal(models.Model):
    """
    WebRTC calls go directly browser-to-browser, but the two browsers first need to
    swap a few setup messages ("offer", "answer"…). The server just passes them along.
    """
    KINDS = ("offer", "answer", "decline", "hangup", "busy", "taken")

    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    call_id = models.CharField(max_length=64, db_index=True)
    kind = models.CharField(max_length=10)
    payload = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["id"]


class Profile(models.Model):
    """Extra information about an account, created by the admin."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True, related_name="profile")
    must_change_password = models.BooleanField(
        default=False, help_text="Ask the user to choose a new password the next time they log in."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    def __str__(self):
        return f"Profile of {self.user}"
