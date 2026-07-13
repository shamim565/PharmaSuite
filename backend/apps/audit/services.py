from apps.audit.models import ActorType, AuditLog


def get_client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(
    *,
    actor,
    action: str,
    entity_type: str,
    entity_id=None,
    before: dict | None = None,
    after: dict | None = None,
    branch=None,
    request=None,
    actor_type: str = ActorType.USER,
) -> AuditLog:
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        actor_type=actor_type,
        branch=branch,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before=before,
        after=after,
        request_id=getattr(request, "request_id", "") if request else "",
        ip=get_client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:300] if request else ""),
    )
