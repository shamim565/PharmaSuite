"""Notification and attachment services."""

import hashlib
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import User, UserStatus
from apps.common.exceptions import APIError
from apps.common.models import Attachment, Notification

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def notify(user, type: str, title: str, body: str = "", deep_link: str = "", payload=None, severity: str = "INFO"):
    """Create an in-app notification for one user."""
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return Notification.objects.create(
        user=user,
        type=type,
        title=title,
        body=body,
        deep_link=deep_link,
        payload=payload or {},
        severity=severity,
    )


def notify_users(users, type: str, title: str, body: str = "", deep_link: str = "", payload=None, severity: str = "INFO"):
    created = 0
    for user in users:
        if notify(user, type, title, body, deep_link, payload, severity):
            created += 1
    return created


ROLE_GROUPS = {
    "stock": ["WAREHOUSE_MANAGER", "BRANCH_MANAGER", "ADMIN", "SUPER_ADMIN", "OWNER"],
    "finance": ["ACCOUNTANT", "BRANCH_MANAGER", "ADMIN", "SUPER_ADMIN", "OWNER"],
    "operations": ["SALES_OPERATOR", "BRANCH_MANAGER", "ADMIN", "SUPER_ADMIN", "OWNER"],
}


def role_users(group: str):
    codes = ROLE_GROUPS.get(group, [])
    return (
        User.objects.filter(user_roles__role__code__in=codes, status=UserStatus.ACTIVE)
        .distinct()
    )


def mark_read(notification: Notification, user) -> Notification:
    if notification.user_id != user.id:
        raise APIError("PERMISSION_DENIED", "You can only read your own notifications.", status_code=403)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at", "updated_at"])
    return notification


def mark_all_read(user) -> int:
    return Notification.objects.filter(user=user, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )


# --------------------------------------------------------------------------- attachments


def _media_root() -> Path:
    return Path(getattr(settings, "MEDIA_ROOT", Path(settings.BASE_DIR) / "media"))


def upload_attachment(*, file, owner_type: str, owner_id, actor) -> Attachment:
    import uuid as uuid_module

    content_type = getattr(file, "content_type", "") or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise APIError(
            "UNSUPPORTED_FILE_TYPE",
            "Only PDF, JPG, PNG, WEBP, CSV and XLSX files are allowed.",
            status_code=400,
        )
    size = file.size
    if size > MAX_UPLOAD_BYTES:
        raise APIError("FILE_TOO_LARGE", "File exceeds the 10 MB limit.", status_code=400)

    original_name = getattr(file, "name", "file") or "file"
    safe_name = Path(original_name).name[:255]
    key_dir = _media_root() / "attachments" / str(owner_id)
    key_dir.mkdir(parents=True, exist_ok=True)
    storage_key = str(uuid_module.uuid4()) + "_" + safe_name
    destination = key_dir / storage_key

    with destination.open("wb") as out:
        for chunk in file.chunks():
            out.write(chunk)

    checksum = hashlib.sha256(destination.read_bytes()).hexdigest()

    return Attachment.objects.create(
        owner_type=owner_type,
        owner_id=owner_id,
        file_name=safe_name,
        content_type=content_type,
        size_bytes=size,
        storage_key=str(destination.relative_to(_media_root())),
        checksum=checksum,
        uploaded_by=actor if getattr(actor, "is_authenticated", False) else None,
    )


def attachment_path(attachment: Attachment) -> Path:
    return _media_root() / attachment.storage_key