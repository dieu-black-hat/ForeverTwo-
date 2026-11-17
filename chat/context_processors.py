from django.conf import settings
from django.urls import reverse


def site(request):
    """Values available in every template."""
    context = {"SITE_NAME": settings.SITE_NAME}
    if request.user.is_authenticated:
        context["call_config"] = {
            "iceServers": settings.CHAT_ICE_SERVERS,
            "signalUrl": reverse("api_call_signal"),
            "pollUrl": reverse("api_call_poll"),
            "sendUrl": reverse("api_send", args=["__room__"]),
            "me": request.user.username,
        }
    return context
