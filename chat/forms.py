import secrets

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator

from .models import Room

User = get_user_model()


def generate_password(length=10):
    """A random, easy-to-type password (no confusing characters like 0/O or 1/l)."""
    letters = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ"
    digits = "23456789"
    while True:
        password = "".join(secrets.choice(letters + digits) for _ in range(length))
        if any(c in digits for c in password) and any(c in letters for c in password):
            return password


class CreateUserForm(forms.Form):
    """Used by the admin on the "Manage users" page."""
    username = forms.CharField(
        max_length=150,
        validators=[UnicodeUsernameValidator()],
        help_text="Letters, numbers and @ . + - _ only (no spaces).",
        widget=forms.TextInput(attrs={"placeholder": "e.g. grace", "autocomplete": "off"}),
    )
    password = forms.CharField(
        required=False,
        label="Temporary password",
        help_text="Leave empty and a strong password is created for you. "
                  "The person will choose their own password at first login.",
        widget=forms.TextInput(attrs={"placeholder": "Leave empty to generate one", "autocomplete": "off"}),
    )
    is_admin = forms.BooleanField(required=False, label="Make this person an admin too")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean_password(self):
        password = self.cleaned_data.get("password", "").strip()
        if password:
            validate_password(password)
        return password or generate_password()


class RoomForm(forms.ModelForm):
    invite = forms.CharField(
        required=False,
        label="Invite people",
        help_text="Usernames separated by commas (only for private rooms).",
        widget=forms.TextInput(attrs={"placeholder": "e.g. alice, bob"}),
    )

    class Meta:
        model = Room
        fields = ["name", "description", "is_private"]
        labels = {"is_private": "Make this room private"}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Study group", "autofocus": True}),
            "description": forms.TextInput(attrs={"placeholder": "What is this room about? (optional)"}),
        }

    def clean_invite(self):
        names = {n.strip() for n in self.cleaned_data.get("invite", "").split(",") if n.strip()}
        if not names:
            return []
        users = list(User.objects.filter(username__in=names))
        missing = names - {u.username for u in users}
        if missing:
            raise forms.ValidationError(f"These users don't exist: {', '.join(sorted(missing))}")
        return users
