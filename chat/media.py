"""
Helpers for shared files (photos, videos, documents, voice notes).

- `classify_upload` decides what kind of message a file becomes and checks it is allowed.
- `ranged_file_response` sends a file to the browser and supports "Range" requests,
  which video players need to jump forward/backward.
"""
import mimetypes
import os
import re

from django.conf import settings
from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from django.utils.http import content_disposition_header

IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
VIDEO_TYPES = {".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".ogv": "video/ogg"}
AUDIO_TYPES = {
    ".webm": "audio/webm", ".ogg": "audio/ogg", ".oga": "audio/ogg", ".m4a": "audio/mp4",
    ".mp4": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".aac": "audio/aac",
}
# Programs that could harm someone's computer if they open them.
BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".vbs", ".ps1", ".pif", ".cpl"}

MB = 1024 * 1024


class UploadError(ValueError):
    pass


def size_limit(kind):
    return {
        "image": settings.CHAT_MAX_IMAGE_MB,
        "video": settings.CHAT_MAX_VIDEO_MB,
        "voice": settings.CHAT_MAX_VOICE_MB,
    }.get(kind, settings.CHAT_MAX_FILE_MB) * MB


def classify_upload(upload, voice=False):
    """Return (kind, mime) for an uploaded file or raise UploadError with a friendly message."""
    ext = os.path.splitext(upload.name)[1].lower()

    if voice:
        if ext not in AUDIO_TYPES:
            raise UploadError("Unsupported voice note format.")
        kind, mime = "voice", AUDIO_TYPES[ext]
    elif ext in BLOCKED_EXTENSIONS:
        raise UploadError("This type of file is not allowed for safety reasons.")
    elif ext in IMAGE_TYPES:
        try:
            from PIL import Image

            with Image.open(upload) as img:
                img.verify()  # checks it really is a picture
        except Exception:
            raise UploadError("This picture seems to be damaged or is not a real image.")
        finally:
            upload.seek(0)
        kind, mime = "image", IMAGE_TYPES[ext]
    elif ext in VIDEO_TYPES:
        kind, mime = "video", VIDEO_TYPES[ext]
    else:
        kind, mime = "file", mimetypes.guess_type(upload.name)[0] or "application/octet-stream"

    if upload.size > size_limit(kind):
        raise UploadError(f"File is too big. The limit for this type is {size_limit(kind) // MB} MB.")
    if upload.size == 0:
        raise UploadError("The file is empty.")
    return kind, mime


def _file_chunks(handle, length, chunk_size=64 * 1024):
    try:
        while length > 0:
            data = handle.read(min(chunk_size, length))
            if not data:
                break
            length -= len(data)
            yield data
    finally:
        handle.close()


def ranged_file_response(request, path, content_type, filename, as_attachment):
    size = os.path.getsize(path)
    match = re.match(r"^bytes=(\d*)-(\d*)$", request.headers.get("Range", "").strip())

    if match and (match.group(1) or match.group(2)):
        if match.group(1):
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else size - 1
        else:  # "bytes=-500" means "the last 500 bytes"
            start, end = max(size - int(match.group(2)), 0), size - 1
        end = min(end, size - 1)
        if start >= size or start > end:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response
        handle = open(path, "rb")
        handle.seek(start)
        length = end - start + 1
        response = StreamingHttpResponse(_file_chunks(handle, length), status=206, content_type=content_type)
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
        response["Content-Length"] = str(length)
    else:
        response = FileResponse(open(path, "rb"), content_type=content_type)

    response["Accept-Ranges"] = "bytes"
    response["Content-Disposition"] = content_disposition_header(as_attachment, filename)
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; media-src 'self'; sandbox"
    response["Cache-Control"] = "private, max-age=86400"
    return response
