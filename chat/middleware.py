"""
If the admin created your account (or reset your password), you must choose
your own password before you can use the chat.
"""
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from .models import Profile


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not request.path.startswith("/static/"):
            allowed = {reverse("change_password"), reverse("logout")}
            if request.path not in allowed and Profile.objects.filter(user=user, must_change_password=True).exists():
                if request.path.startswith("/api/"):
                    return JsonResponse({"error": "Please choose a new password first."}, status=403)
                return redirect("change_password")
        return self.get_response(request)
