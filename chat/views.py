"""
Views = the Python functions that answer each web address.

Page views return HTML.  The `api_*` views return JSON and are called by
static/chat/app.js and static/chat/call.js every second or two
(this technique is called "polling" and works on any hosting provider).
"""
import json
import random

from django.conf import settings
from django.contrib import messages as flash
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import CreateUserForm, RoomForm, generate_password
from .media import UploadError, classify_upload, ranged_file_response
from .stickers import STICKER_CODES, sticker_list
from .models import CallSignal, Message, Presence, Profile, ReadMarker, Room, Typing, avatar_color

User = get_user_model()


# ---------------------------------------------------------------- helpers ---
def _get_room_or_404(user, slug):
    room = get_object_or_404(Room, slug=slug)
    if not room.can_access(user):
        raise Http404("Room not found")
    return room


def visible_people(user):
    """Admins see everyone; normal users only see the admins."""
    people = User.objects.filter(is_active=True).exclude(pk=user.pk)
    if not user.is_staff:
        people = people.filter(is_staff=True)
    return people.order_by("-is_superuser", "username")


def accessible_rooms(user):
    """Every room this user is allowed to open (see Room.can_access)."""
    candidates = Room.objects.filter(members=user).prefetch_related("members")
    return [r for r in candidates if r.can_access(user)]


def _sidebar_context(user):
    online = Presence.online_user_ids()
    direct_rooms = [
        r for r in Room.objects.filter(is_direct=True, members=user).prefetch_related("members").order_by("-created_at")
        if r.can_access(user)
    ]
    is_admin = user.is_staff
    return {
        "public_rooms": Room.objects.filter(is_private=False) if is_admin else Room.objects.none(),
        "private_rooms": (
            Room.objects.filter(is_private=True, is_direct=False, members=user) if is_admin else Room.objects.none()
        ),
        "direct_rooms": [{"room": r, "name": r.display_name_for(user)} for r in direct_rooms],
        "people": [
            {"user": p, "online": p.pk in online, "color": avatar_color(p.username)} for p in visible_people(user)
        ],
        "my_color": avatar_color(user.username),
    }


def _seen_id(room, user):
    """In a direct message: the newest message the OTHER person has read."""
    if not room.is_direct:
        return 0
    other = room.other_member(user)
    if not other:
        return 0
    return ReadMarker.objects.filter(room=room, user=other).values_list("last_read_id", flat=True).first() or 0


def _reply_target(request, room):
    """The message being replied to, if any (must be in the same room)."""
    try:
        reply_id = int(request.POST.get("reply_to") or 0)
    except ValueError:
        return None
    if not reply_id:
        return None
    return room.messages.filter(pk=reply_id, deleted_at__isnull=True).first()


def _after_new_message(user, room, message):
    if not room.is_private:
        room.members.add(user)
    ReadMarker.mark(user, room, message.id)
    Presence.touch(user)
    Typing.objects.filter(user=user, room=room).delete()


# ----------------------------------------------------------------- pages ---
def _admin_only(user):
    return user.is_authenticated and user.is_active and user.is_staff


@login_required
def change_password(request):
    """Every user can change their own password here."""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)  # stay logged in after the change
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password"])
        flash.success(request, "Your password has been changed. 🔒")
        return redirect("home")
    context = _sidebar_context(request.user)
    context.update({"form": form, "forced": profile.must_change_password})
    return render(request, "chat/change_password.html", context)


@login_required
@user_passes_test(_admin_only)
def manage_users(request):
    """Admin page: create accounts and see everyone."""
    form = CreateUserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        password = form.cleaned_data["password"]
        user = User.objects.create_user(form.cleaned_data["username"], password=password)
        user.is_staff = form.cleaned_data["is_admin"]
        user.save()
        Profile.objects.update_or_create(
            user=user, defaults={"must_change_password": False, "created_by": request.user}
        )
        request.session["new_credentials"] = {"username": user.username, "password": password, "action": "created"}
        flash.success(request, f"Account for {user.username} created.")
        return redirect("manage_users")

    credentials = request.session.pop("new_credentials", None)
    share_text = ""
    login_url = request.build_absolute_uri(reverse("login"))
    if credentials:
        share_text = (
            f"Hello {credentials['username']} 👋\n"
            f"Here is your {settings.SITE_NAME} account:\n\n"
            f"🔗 Link: {login_url}\n"
            f"👤 Username: {credentials['username']}\n"
            f"🔑 Password: {credentials['password']}\n\n"
            f"You can change your password anytime with the 🔑 key icon."
        )

    online = Presence.online_user_ids()
    users = []
    for u in User.objects.order_by("-is_active", "username"):
        profile = Profile.objects.filter(user=u).first()
        users.append(
            {
                "user": u,
                "color": avatar_color(u.username),
                "online": u.pk in online,
                "pending": u.last_login is None,
                "protected": u.pk == request.user.pk or (u.is_superuser and not request.user.is_superuser),
            }
        )
    context = _sidebar_context(request.user)
    context.update(
        {"form": form, "users": users, "credentials": credentials, "share_text": share_text, "login_url": login_url}
    )
    return render(request, "chat/manage_users.html", context)


@login_required
@user_passes_test(_admin_only)
@require_POST
def user_action(request, user_id):
    """Admin actions on one account: reset password, deactivate, activate."""
    target = get_object_or_404(User, pk=user_id)
    action = request.POST.get("action")
    if target.pk == request.user.pk or (target.is_superuser and not request.user.is_superuser):
        flash.error(request, "You can't change this account here.")
        return redirect("manage_users")

    if action == "reset":
        password = generate_password()
        target.set_password(password)
        target.save()
        Profile.objects.update_or_create(user=target, defaults={"must_change_password": False})
        request.session["new_credentials"] = {"username": target.username, "password": password, "action": "reset"}
        flash.success(request, f"New password created for {target.username}.")
    elif action == "deactivate":
        target.is_active = False
        target.save(update_fields=["is_active"])
        flash.info(request, f"{target.username} can no longer log in.")
    elif action == "delete":
        name = target.username
        # Remove their private conversations too, then the account (and its messages).
        Room.objects.filter(is_direct=True, members=target).delete()
        target.delete()
        flash.success(request, f"{name}'s account and messages were deleted.")
    elif action == "activate":
        target.is_active = True
        target.save(update_fields=["is_active"])
        flash.success(request, f"{target.username} can log in again.")
    else:
        flash.error(request, "Unknown action.")
    return redirect("manage_users")


@login_required
def home(request):
    if not request.user.is_staff:
        # Normal users go straight to their chat with the admin.
        admin = visible_people(request.user).first()
        if admin:
            return redirect("direct_message", username=admin.username)
        return render(request, "chat/no_admin.html", _sidebar_context(request.user))
    room = Room.objects.filter(is_private=False).order_by("created_at").first()
    if room:
        return redirect("room", slug=room.slug)
    return redirect("create_room")


@login_required
def room_view(request, slug):
    room = _get_room_or_404(request.user, slug)
    if not room.is_private:
        room.members.add(request.user)  # joining a public room = becoming a member

    recent = list(
        room.messages.select_related("user", "reply_to__user").order_by("-id")[: settings.CHAT_HISTORY_SIZE]
    )[::-1]
    if recent:
        ReadMarker.mark(request.user, room, recent[-1].id)
    Presence.touch(request.user)

    other = room.other_member(request.user) if room.is_direct else None
    context = _sidebar_context(request.user)
    context.update(
        {
            "room": room,
            "room_title": room.display_name_for(request.user),
            "other": other,
            "other_color": avatar_color(other.username) if other else None,
            "member_count": room.members.count(),
            "initial_messages": [m.to_dict(request.user) for m in recent],
            "chat_config": {
                "slug": room.slug,
                "isDirect": room.is_direct,
                "messagesUrl": reverse("api_messages", args=[room.slug]),
                "sendUrl": reverse("api_send", args=[room.slug]),
                "uploadUrl": reverse("api_upload", args=[room.slug]),
                "typingUrl": reverse("api_typing", args=[room.slug]),
                "screenshotUrl": reverse("api_screenshot", args=[room.slug]),
                "deleteUrl": reverse("api_delete", args=[0]),
                "seenId": _seen_id(room, request.user),
                "maxLength": settings.CHAT_MAX_MESSAGE_LENGTH,
                "maxVoiceSeconds": settings.CHAT_MAX_VOICE_SECONDS,
                "stickers": sticker_list(),
                "limitsMb": {
                    "image": settings.CHAT_MAX_IMAGE_MB,
                    "video": settings.CHAT_MAX_VIDEO_MB,
                    "file": settings.CHAT_MAX_FILE_MB,
                },
                "me": request.user.username,
            },
        }
    )
    return render(request, "chat/room.html", context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def create_room(request):
    form = RoomForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        room = form.save(commit=False)
        room.slug = Room.make_unique_slug(room.name)
        room.created_by = request.user
        room.save()
        room.members.add(request.user, *form.cleaned_data["invite"])
        flash.success(request, f"Room “{room.name}” created.")
        return redirect("room", slug=room.slug)
    context = _sidebar_context(request.user)
    context["form"] = form
    return render(request, "chat/create_room.html", context)


@login_required
def direct_message(request, username):
    other = get_object_or_404(User, username=username, is_active=True)
    if other == request.user:
        return redirect("home")
    if not request.user.is_staff and not other.is_staff:
        raise Http404("You can only message the admin.")
    low, high = sorted([request.user.pk, other.pk])
    room, created = Room.objects.get_or_create(
        slug=f"dm-{low}-{high}",
        defaults={"name": f"DM {low}-{high}", "is_private": True, "is_direct": True, "created_by": request.user},
    )
    if created:
        room.members.add(request.user, other)
    return redirect("room", slug=room.slug)


@login_required
@require_POST
def leave_room(request, slug):
    room = _get_room_or_404(request.user, slug)
    if room.is_direct:
        flash.error(request, "You can't leave a direct message.")
        return redirect("room", slug=slug)
    room.members.remove(request.user)
    flash.info(request, f"You left “{room.name}”.")
    return redirect("home")


@login_required
@require_GET
def message_file(request, message_id):
    """Sends a shared photo/video/file — only to people allowed in that room."""
    msg = get_object_or_404(Message.objects.select_related("room"), pk=message_id, deleted_at__isnull=True)
    if not msg.attachment or not msg.room.can_access(request.user):
        raise Http404
    try:
        path = msg.attachment.path
        download = request.GET.get("download") == "1" or msg.kind == Message.FILE
        return ranged_file_response(request, path, msg.mime or "application/octet-stream", msg.file_name or "file", download)
    except FileNotFoundError:
        raise Http404


# ------------------------------------------------------------- JSON API ---
@login_required
@require_GET
def api_messages(request, slug):
    """New messages after ?after=<id>, plus deletions, who's typing and "Seen"."""
    room = _get_room_or_404(request.user, slug)
    try:
        after = max(int(request.GET.get("after", 0)), 0)
    except ValueError:
        after = 0
    new = list(room.messages.filter(id__gt=after).select_related("user", "reply_to__user").order_by("id")[:100])
    if new:
        ReadMarker.mark(request.user, room, new[-1].id)
    Presence.touch(request.user)

    now = timezone.now()
    deleted = list(
        room.messages.filter(deleted_at__gte=now - timezone.timedelta(seconds=90), id__lte=after)
        .values_list("id", flat=True)
    )
    typing = list(
        Typing.objects.filter(room=room, at__gte=now - timezone.timedelta(seconds=5))
        .exclude(user=request.user)
        .values_list("user__username", flat=True)
    )
    return JsonResponse(
        {
            "messages": [m.to_dict(request.user) for m in new],
            "deleted": deleted,
            "typing": typing,
            "seen_id": _seen_id(room, request.user),
        }
    )


@login_required
@require_POST
def api_send(request, slug):
    room = _get_room_or_404(request.user, slug)
    content = request.POST.get("content", "").strip()
    kind = request.POST.get("kind", Message.TEXT)
    if kind not in (Message.TEXT, Message.CALL, Message.STICKER) or (kind == Message.CALL and not room.is_direct):
        return JsonResponse({"error": "Invalid message type."}, status=400)
    if kind == Message.STICKER and content not in STICKER_CODES:
        return JsonResponse({"error": "Unknown sticker."}, status=400)
    if not content:
        return JsonResponse({"error": "Message is empty."}, status=400)
    if len(content) > (100 if kind == Message.CALL else settings.CHAT_MAX_MESSAGE_LENGTH):
        return JsonResponse(
            {"error": f"Message is too long (max {settings.CHAT_MAX_MESSAGE_LENGTH} characters)."}, status=400
        )
    message = Message.objects.create(
        room=room, user=request.user, kind=kind, content=content,
        reply_to=_reply_target(request, room) if kind in (Message.TEXT, Message.STICKER) else None,
    )
    _after_new_message(request.user, room, message)
    return JsonResponse({"message": message.to_dict(request.user)}, status=201)


@login_required
@require_POST
def api_upload(request, slug):
    """Receives a photo, video, document or voice note."""
    room = _get_room_or_404(request.user, slug)
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "No file received."}, status=400)
    is_voice = request.POST.get("voice") == "1"
    try:
        kind, mime = classify_upload(upload, voice=is_voice)
    except UploadError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    caption = request.POST.get("caption", "").strip()[: settings.CHAT_MAX_MESSAGE_LENGTH]
    try:
        duration = min(max(int(float(request.POST.get("duration", 0))), 0), 60 * 60)
    except ValueError:
        duration = 0

    message = Message(
        room=room, user=request.user, kind=kind, content="" if is_voice else caption,
        file_name=upload.name[:255], file_size=upload.size, mime=mime, duration=duration,
        reply_to=_reply_target(request, room),
    )
    message.attachment.save(upload.name, upload, save=False)
    message.save()
    _after_new_message(request.user, room, message)
    return JsonResponse({"message": message.to_dict(request.user)}, status=201)


@login_required
@require_POST
def api_screenshot(request, slug):
    """
    The browser noticed a screenshot key (e.g. Print Screen). We post a small
    notice in the chat so everyone knows. At most one notice per 30 seconds.
    """
    room = _get_room_or_404(request.user, slug)
    recent = room.messages.filter(
        user=request.user, kind=Message.ALERT, created_at__gte=timezone.now() - timezone.timedelta(seconds=30)
    ).exists()
    if recent:
        return JsonResponse({"ok": True, "message": None})
    message = Message.objects.create(
        room=room, user=request.user, kind=Message.ALERT, content=f"{request.user.username} took a screenshot"
    )
    ReadMarker.mark(request.user, room, message.id)
    return JsonResponse({"ok": True, "message": message.to_dict(request.user)}, status=201)


@login_required
@require_POST
def api_delete(request, message_id):
    """Delete one of your own messages for everyone."""
    msg = get_object_or_404(Message, pk=message_id, user=request.user, deleted_at__isnull=True)
    msg.soft_delete()
    return JsonResponse({"message": msg.to_dict(request.user)})


@login_required
@require_POST
def api_typing(request, slug):
    room = _get_room_or_404(request.user, slug)
    Typing.objects.update_or_create(user=request.user, room=room, defaults={"at": timezone.now()})
    return JsonResponse({"ok": True})


@login_required
@require_GET
def api_sidebar(request):
    """Unread counts for every room you are in, plus who is online."""
    user = request.user
    Presence.touch(user)
    markers = dict(ReadMarker.objects.filter(user=user).values_list("room_id", "last_read_id"))
    rooms = []
    rooms_i_can_open = accessible_rooms(user)
    for room in rooms_i_can_open:
        unread = (
            Message.objects.filter(room=room, id__gt=markers.get(room.id, 0), deleted_at__isnull=True)
            .exclude(user=user)
            .count()
        )
        other = room.other_member(user) if room.is_direct else None
        rooms.append(
            {
                "slug": room.slug,
                "name": room.display_name_for(user),
                "kind": "direct" if room.is_direct else ("private" if room.is_private else "public"),
                "url": reverse("room", args=[room.slug]),
                "unread": unread,
                "color": avatar_color(other.username) if other else None,
            }
        )
    online = Presence.online_user_ids()
    online_names = list(visible_people(user).filter(pk__in=online).values_list("username", flat=True))

    # New messages from other people since ?since=<id>, used for desktop pop-up notifications.
    my_messages = Message.objects.filter(room__in=[r.pk for r in rooms_i_can_open])
    cursor = my_messages.aggregate(m=Max("id"))["m"] or 0
    latest = []
    try:
        since = int(request.GET["since"])
    except (KeyError, ValueError):
        since = None
    if since is not None:
        for m in (
            my_messages.filter(id__gt=since, deleted_at__isnull=True)
            .exclude(user=user)
            .exclude(kind=Message.CALL)
            .select_related("user", "room")
            .prefetch_related("room__members")
            .order_by("id")[:10]
        ):
            latest.append(
                {
                    "id": m.id,
                    "room": m.room.slug,
                    "room_name": m.room.display_name_for(user),
                    "is_direct": m.room.is_direct,
                    "sender": m.user.username,
                    "preview": _preview(m),
                    "url": reverse("room", args=[m.room.slug]),
                }
            )
    return JsonResponse({"rooms": rooms, "online": online_names, "cursor": cursor, "latest": latest})


def _preview(message):
    """Short text for a notification, e.g. "📷 Photo" or the first words of a message."""
    return message.preview_text()


# ------------------------------------------------------------ calls API ---
@login_required
@require_POST
def api_call_signal(request):
    """Pass one call-setup message to the other person in a direct message."""
    room = _get_room_or_404(request.user, request.POST.get("room", ""))
    kind = request.POST.get("kind", "")
    call_id = request.POST.get("call_id", "")[:64]
    payload = request.POST.get("payload", "")
    if not room.is_direct:
        return JsonResponse({"error": "Calls are available in direct messages."}, status=400)
    if kind not in CallSignal.KINDS or not call_id or len(payload) > 100_000:
        return JsonResponse({"error": "Invalid call signal."}, status=400)
    other = room.other_member(request.user)
    if not other:
        return JsonResponse({"error": "Nobody to call."}, status=400)

    CallSignal.objects.create(
        room=room, sender=request.user, recipient=other, call_id=call_id, kind=kind, payload=payload
    )
    if kind in ("answer", "decline"):
        # Tell your OTHER open tabs/devices to stop ringing.
        CallSignal.objects.create(
            room=room, sender=request.user, recipient=request.user, call_id=call_id, kind="taken"
        )
    if random.random() < 0.05:  # tidy up old signals now and then
        CallSignal.objects.filter(created_at__lt=timezone.now() - timezone.timedelta(hours=1)).delete()
    return JsonResponse({"ok": True})


@login_required
@require_GET
def api_call_poll(request):
    """Call signals waiting for you. Without ?after, just returns the current cursor."""
    latest = CallSignal.objects.aggregate(m=Max("id"))["m"] or 0
    if "after" not in request.GET:
        return JsonResponse({"cursor": latest, "signals": []})
    try:
        after = int(request.GET["after"])
    except ValueError:
        after = latest
    signals = (
        CallSignal.objects.filter(
            recipient=request.user, id__gt=after, created_at__gte=timezone.now() - timezone.timedelta(seconds=60)
        )
        .select_related("sender", "room")
        .order_by("id")
    )
    data = []
    for s in signals:
        item = {
            "id": s.id, "kind": s.kind, "call_id": s.call_id, "room": s.room.slug,
            "sender": s.sender.username, "color": avatar_color(s.sender.username), "payload": s.payload,
        }
        data.append(item)
    cursor = max([after] + [s["id"] for s in data])
    return JsonResponse({"cursor": cursor, "signals": data})
