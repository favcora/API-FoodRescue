from datetime import datetime, timezone


def utcnow() -> datetime:
    """Data/hora atual em UTC, sem fuso (é assim que gravamos no banco)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_naive(dt: datetime) -> datetime:
    """Converte qualquer datetime para UTC sem fuso. Datas sem fuso são tratadas como UTC."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
