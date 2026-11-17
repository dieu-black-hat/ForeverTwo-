"""Run with:  python manage.py test"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Message, Room

User = get_user_model()


class ChatTests(TestCase):
    def setUp(self):
        # Group rooms are for admins, so these two are admins.
        self.alice = User.objects.create_user("alice", password="pass-12345-x", is_staff=True)
        self.bob = User.objects.create_user("bob", password="pass-12345-x", is_staff=True)
        self.room = Room.objects.create(name="Lobby", slug="lobby")

    def test_login_required(self):
        res = self.client.get(reverse("room", args=["lobby"]))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse("login"), res.url)

    def test_public_signup_removed(self):
        self.assertEqual(self.client.get("/signup/").status_code, 404)
    def test_send_and_poll(self):
        self.client.login(username="alice", password="pass-12345-x")
        res = self.client.post(reverse("api_send", args=["lobby"]), {"content": "Hello <b>world</b>"})
        self.assertEqual(res.status_code, 201)
        msg_id = res.json()["message"]["id"]

        self.client.login(username="bob", password="pass-12345-x")
        res = self.client.get(reverse("api_messages", args=["lobby"]), {"after": 0})
        data = res.json()["messages"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["content"], "Hello <b>world</b>")
        self.assertFalse(data[0]["is_mine"])
        res = self.client.get(reverse("api_messages", args=["lobby"]), {"after": msg_id})
        self.assertEqual(res.json()["messages"], [])

    def test_empty_and_too_long_rejected(self):
        self.client.login(username="alice", password="pass-12345-x")
        self.assertEqual(self.client.post(reverse("api_send", args=["lobby"]), {"content": "  "}).status_code, 400)
        self.assertEqual(
            self.client.post(reverse("api_send", args=["lobby"]), {"content": "x" * 5000}).status_code, 400
        )

    def test_private_room_hidden_from_non_members(self):
        secret = Room.objects.create(name="Secret", slug="secret", is_private=True)
        secret.members.add(self.alice)
        self.client.login(username="bob", password="pass-12345-x")
        self.assertEqual(self.client.get(reverse("room", args=["secret"])).status_code, 404)
        self.assertEqual(self.client.post(reverse("api_send", args=["secret"]), {"content": "hi"}).status_code, 404)

    def test_direct_message_and_unread(self):
        self.client.login(username="alice", password="pass-12345-x")
        res = self.client.get(reverse("direct_message", args=["bob"]))
        dm = Room.objects.get(is_direct=True)
        self.assertRedirects(res, reverse("room", args=[dm.slug]))
        self.client.post(reverse("api_send", args=[dm.slug]), {"content": "hey bob"})

        self.client.login(username="bob", password="pass-12345-x")
        rooms = {r["slug"]: r for r in self.client.get(reverse("api_sidebar")).json()["rooms"]}
        self.assertEqual(rooms[dm.slug]["unread"], 1)
        self.assertEqual(rooms[dm.slug]["name"], "alice")
        self.client.get(reverse("room", args=[dm.slug]))  # reading clears unread
        rooms = {r["slug"]: r for r in self.client.get(reverse("api_sidebar")).json()["rooms"]}
        self.assertEqual(rooms[dm.slug]["unread"], 0)

    def test_create_private_room_with_invite(self):
        self.client.login(username="alice", password="pass-12345-x")
        res = self.client.post(
            reverse("create_room"), {"name": "Study Group", "description": "", "is_private": "on", "invite": "bob"}
        )
        room = Room.objects.get(name="Study Group")
        self.assertRedirects(res, reverse("room", args=[room.slug]))
        self.assertTrue(room.members.filter(username="bob").exists())

    def test_room_page_renders(self):
        Message.objects.create(room=self.room, user=self.bob, content="hi")
        self.client.login(username="alice", password="pass-12345-x")
        res = self.client.get(reverse("room", args=["lobby"]))
        self.assertContains(res, "initial-messages")
        self.assertContains(res, "Lobby")


# ---------------------------------------------------------------- media ---
import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from .models import CallSignal

TEMP_MEDIA = tempfile.mkdtemp()


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "purple").save(buf, "PNG")
    return buf.getvalue()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class MediaAndCallTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pass-12345-x", is_staff=True)  # admin
        self.bob = User.objects.create_user("bob", password="pass-12345-x")  # normal user
        self.eve = User.objects.create_user("eve", password="pass-12345-x")  # outsider
        self.dm = Room.objects.create(name="DM", slug="dm-1-2", is_private=True, is_direct=True)
        self.dm.members.add(self.alice, self.bob)
        self.client.login(username="alice", password="pass-12345-x")

    def upload(self, name, data, content_type, **extra):
        f = SimpleUploadedFile(name, data, content_type=content_type)
        return self.client.post(reverse("api_upload", args=[self.dm.slug]), {"file": f, **extra})

    def test_photo_upload_and_protected_download(self):
        res = self.upload("cat.png", _png_bytes(), "image/png", caption="Look!")
        self.assertEqual(res.status_code, 201)
        msg = res.json()["message"]
        self.assertEqual(msg["kind"], "image")
        self.assertEqual(msg["content"], "Look!")
        self.assertEqual(self.client.get(msg["file_url"]).status_code, 200)
        # someone outside the conversation can't download it
        self.client.login(username="eve", password="pass-12345-x")
        self.assertEqual(self.client.get(msg["file_url"]).status_code, 404)

    def test_fake_image_rejected(self):
        res = self.upload("evil.png", b"<script>alert(1)</script>", "image/png")
        self.assertEqual(res.status_code, 400)

    def test_blocked_extension(self):
        self.assertEqual(self.upload("virus.exe", b"MZ....", "application/octet-stream").status_code, 400)

    def test_document_and_video(self):
        self.assertEqual(self.upload("notes.pdf", b"%PDF-1.4 test", "application/pdf").json()["message"]["kind"], "file")
        res = self.upload("clip.mp4", b"\x00\x00\x00\x18ftypmp42" + b"0" * 5000, "video/mp4")
        msg = res.json()["message"]
        self.assertEqual(msg["kind"], "video")
        ranged = self.client.get(msg["file_url"], HTTP_RANGE="bytes=0-99")
        self.assertEqual(ranged.status_code, 206)
        self.assertEqual(ranged["Content-Range"], f"bytes 0-99/{msg['file_size']}")
        self.assertEqual(len(b"".join(ranged.streaming_content)), 100)

    def test_voice_note(self):
        res = self.upload("voice-note.webm", b"\x1aE\xdf\xa3" + b"0" * 2000, "audio/webm", voice="1", duration="7")
        msg = res.json()["message"]
        self.assertEqual((msg["kind"], msg["duration"]), ("voice", 7))

    def test_delete_for_everyone(self):
        msg = self.upload("cat.png", _png_bytes(), "image/png").json()["message"]
        self.client.login(username="bob", password="pass-12345-x")
        self.assertEqual(self.client.post(reverse("api_delete", args=[msg["id"]])).status_code, 404)  # not his
        self.client.login(username="alice", password="pass-12345-x")
        self.assertEqual(self.client.post(reverse("api_delete", args=[msg["id"]])).status_code, 200)
        self.assertEqual(self.client.get(msg["file_url"]).status_code, 404)
        self.client.login(username="bob", password="pass-12345-x")
        data = self.client.get(reverse("api_messages", args=[self.dm.slug]), {"after": msg["id"]}).json()
        self.assertIn(msg["id"], data["deleted"])

    def test_typing_and_seen(self):
        self.client.post(reverse("api_typing", args=[self.dm.slug]))
        sent = self.client.post(reverse("api_send", args=[self.dm.slug]), {"content": "hi"}).json()["message"]
        self.client.login(username="bob", password="pass-12345-x")
        data = self.client.get(reverse("api_messages", args=[self.dm.slug]), {"after": 0}).json()
        self.assertEqual(data["typing"], [])  # sending a message clears "typing"
        self.client.login(username="alice", password="pass-12345-x")
        data = self.client.get(reverse("api_messages", args=[self.dm.slug]), {"after": sent["id"]}).json()
        self.assertEqual(data["seen_id"], sent["id"])

    def test_call_signalling(self):
        cursor = self.client.get(reverse("api_call_poll")).json()["cursor"]
        res = self.client.post(
            reverse("api_call_signal"), {"room": self.dm.slug, "kind": "offer", "call_id": "c1", "payload": "{}"}
        )
        self.assertEqual(res.status_code, 200)
        self.client.login(username="bob", password="pass-12345-x")
        signals = self.client.get(reverse("api_call_poll"), {"after": cursor}).json()["signals"]
        self.assertEqual([(s["kind"], s["sender"]) for s in signals], [("offer", "alice")])
        # outsiders can't signal into the DM; calls only work in DMs
        self.client.login(username="eve", password="pass-12345-x")
        self.assertEqual(
            self.client.post(reverse("api_call_signal"), {"room": self.dm.slug, "kind": "offer", "call_id": "x"}).status_code,
            404,
        )
        self.assertEqual(CallSignal.objects.count(), 1)

    def test_call_record_only_in_dm(self):
        Room.objects.create(name="Lobby", slug="lobby")
        res = self.client.post(reverse("api_send", args=["lobby"]), {"kind": "call", "content": "Audio call · 1:00"})
        self.assertEqual(res.status_code, 400)
        res = self.client.post(reverse("api_send", args=[self.dm.slug]), {"kind": "call", "content": "Audio call · 1:00"})
        self.assertEqual(res.status_code, 201)


# ------------------------------------------------------------- accounts ---
from django.conf import settings as dj_settings

from .models import Profile


class AdminAccountTests(TestCase):
    def setUp(self):
        self.admin = User.objects.get(username=dj_settings.DEFAULT_ADMIN_USERNAME)
        self.client.login(username=self.admin.username, password=dj_settings.DEFAULT_ADMIN_PASSWORD)

    def test_default_admin_created_by_migrate(self):
        self.assertTrue(self.admin.is_superuser and self.admin.is_staff)
        self.assertEqual(self.admin.username, "Hustler")
        self.assertTrue(self.admin.check_password("Hustler@12345"))

    def test_admin_creates_user_who_must_change_password(self):
        res = self.client.post(reverse("manage_users"), {"username": "grace", "password": ""})
        self.assertRedirects(res, reverse("manage_users"), fetch_redirect_response=False)
        page = self.client.get(reverse("manage_users"))
        creds = page.context["credentials"]
        self.assertEqual(creds["username"], "grace")
        self.assertContains(page, creds["password"])
        self.assertContains(page, "wa.me")
        # shown only once
        self.assertIsNone(self.client.get(reverse("manage_users")).context["credentials"])

        self.client.logout()
        self.assertTrue(self.client.login(username="grace", password=creds["password"]))
        self.assertRedirects(self.client.get(reverse("home")), reverse("change_password"))
        self.assertEqual(self.client.get(reverse("api_sidebar")).status_code, 403)
        res = self.client.post(
            reverse("change_password"),
            {"old_password": creds["password"], "new_password1": "Grace-own-pw-2026", "new_password2": "Grace-own-pw-2026"},
        )
        self.assertRedirects(res, reverse("home"), target_status_code=302)
        self.assertFalse(Profile.objects.get(user__username="grace").must_change_password)
        self.assertEqual(self.client.get(reverse("api_sidebar")).status_code, 200)

    def test_duplicate_and_weak_passwords_rejected(self):
        User.objects.create_user("bob", password="x-strong-pass-1")
        res = self.client.post(reverse("manage_users"), {"username": "BOB"})
        self.assertContains(res, "already taken")
        res = self.client.post(reverse("manage_users"), {"username": "carol", "password": "123"})
        self.assertFalse(User.objects.filter(username="carol").exists())

    def test_normal_users_cannot_manage(self):
        User.objects.create_user("bob", password="x-strong-pass-1")
        self.client.login(username="bob", password="x-strong-pass-1")
        self.assertEqual(self.client.get(reverse("manage_users")).status_code, 302)
        self.client.post(reverse("manage_users"), {"username": "hacker"})
        self.assertFalse(User.objects.filter(username="hacker").exists())

    def test_reset_and_deactivate(self):
        bob = User.objects.create_user("bob", password="x-strong-pass-1")
        self.client.post(reverse("user_action", args=[bob.pk]), {"action": "reset"})
        new_pw = self.client.get(reverse("manage_users")).context["credentials"]["password"]
        bob.refresh_from_db()
        self.assertTrue(bob.check_password(new_pw))
        self.client.post(reverse("user_action", args=[bob.pk]), {"action": "deactivate"})
        bob.refresh_from_db()
        self.assertFalse(bob.is_active)
        # the admin can't deactivate themselves
        self.client.post(reverse("user_action", args=[self.admin.pk]), {"action": "deactivate"})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_notification_feed(self):
        bob = User.objects.create_user("bob", password="x-strong-pass-1")
        room = Room.objects.get(slug="general")
        room.members.add(self.admin, bob)
        cursor = self.client.get(reverse("api_sidebar")).json()["cursor"]
        Message.objects.create(room=room, user=bob, content="Are you coming tonight?")
        latest = self.client.get(reverse("api_sidebar"), {"since": cursor}).json()["latest"]
        self.assertEqual(len(latest), 1)
        self.assertEqual((latest[0]["sender"], latest[0]["preview"]), ("bob", "Are you coming tonight?"))



# ------------------------------------------------------------- privacy ---
class PrivacyTests(TestCase):
    """Normal users only see the admin; the admin sees (and can delete) everyone."""

    def setUp(self):
        self.admin = User.objects.get(username=dj_settings.DEFAULT_ADMIN_USERNAME)
        self.grace = User.objects.create_user("grace", password="x-strong-pass-1")
        self.eric = User.objects.create_user("eric", password="x-strong-pass-1")

    def login(self, user):
        self.client.force_login(user)

    def test_normal_user_sees_only_admin(self):
        self.login(self.grace)
        res = self.client.get(reverse("home"))
        self.assertRedirects(res, reverse("direct_message", args=[self.admin.username]), target_status_code=302)
        page = self.client.get(reverse("direct_message", args=[self.admin.username]), follow=True)
        names = [p["user"].username for p in page.context["people"]]
        self.assertEqual(names, [self.admin.username])
        self.assertNotContains(page, "eric")
        self.assertNotContains(page, "General")

    def test_normal_user_cannot_reach_others(self):
        self.login(self.grace)
        self.assertEqual(self.client.get(reverse("direct_message", args=["eric"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("room", args=["general"])).status_code, 404)
        self.assertEqual(self.client.post(reverse("api_send", args=["general"]), {"content": "hi"}).status_code, 404)
        self.assertEqual(self.client.get(reverse("create_room")).status_code, 302)
        # an old DM between two normal users is also blocked
        old = Room.objects.create(name="old", slug="dm-old", is_private=True, is_direct=True)
        old.members.add(self.grace, self.eric)
        self.assertEqual(self.client.get(reverse("room", args=["dm-old"])).status_code, 404)
        data = self.client.get(reverse("api_sidebar")).json()
        self.assertNotIn("dm-old", [r["slug"] for r in data["rooms"]])
        self.assertNotIn("eric", data["online"])

    def test_admin_sees_everyone(self):
        self.login(self.admin)
        page = self.client.get(reverse("room", args=["general"]))
        names = {p["user"].username for p in page.context["people"]}
        self.assertEqual(names, {"grace", "eric"})

    def test_admin_deletes_user(self):
        self.login(self.grace)
        self.client.get(reverse("direct_message", args=[self.admin.username]))
        dm = Room.objects.get(is_direct=True)
        self.client.post(reverse("api_send", args=[dm.slug]), {"content": "hello admin"})
        self.login(self.admin)
        res = self.client.post(reverse("user_action", args=[self.grace.pk]), {"action": "delete"})
        self.assertRedirects(res, reverse("manage_users"))
        self.assertFalse(User.objects.filter(username="grace").exists())
        self.assertFalse(Room.objects.filter(pk=dm.pk).exists())
        # normal users can't delete anyone
        self.login(self.eric)
        self.client.post(reverse("user_action", args=[self.admin.pk]), {"action": "delete"})
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())


# -------------------------------------------------------------- replies ---
class ReplyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.get(username=dj_settings.DEFAULT_ADMIN_USERNAME)
        self.grace = User.objects.create_user("grace", password="x-strong-pass-1")
        self.client.force_login(self.grace)
        self.client.get(reverse("direct_message", args=[self.admin.username]))
        self.dm = Room.objects.get(is_direct=True)

    def send(self, content, **extra):
        return self.client.post(reverse("api_send", args=[self.dm.slug]), {"content": content, **extra}).json()

    def test_reply_includes_quote(self):
        first = self.send("Are we meeting at 7?")["message"]
        self.client.force_login(self.admin)
        reply = self.send("Yes, at the library", reply_to=first["id"])["message"]
        self.assertEqual(reply["reply"]["id"], first["id"])
        self.assertEqual(reply["reply"]["user"], "grace")
        self.assertEqual(reply["reply"]["text"], "Are we meeting at 7?")
        # also visible when polling
        polled = self.client.get(reverse("api_messages", args=[self.dm.slug]), {"after": first["id"]}).json()
        self.assertEqual(polled["messages"][0]["reply"]["id"], first["id"])

    def test_cannot_reply_to_message_in_another_room(self):
        other = Room.objects.get(slug="general")
        foreign = Message.objects.create(room=other, user=self.admin, content="secret")
        reply = self.send("hi", reply_to=foreign.id)["message"]
        self.assertNotIn("reply", reply)

    def test_deleted_original_shows_placeholder(self):
        first = self.send("oops")["message"]
        reply = self.send("answer", reply_to=first["id"])["message"]
        self.client.post(reverse("api_delete", args=[first["id"]]))
        data = self.client.get(reverse("api_messages", args=[self.dm.slug]), {"after": 0}).json()
        quoted = [m for m in data["messages"] if m["id"] == reply["id"]][0]["reply"]
        self.assertEqual(quoted["text"], "This message was deleted")
