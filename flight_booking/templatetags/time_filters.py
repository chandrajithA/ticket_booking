from django import template

register = template.Library()

@register.filter
def format_duration(value):
    if not value:
        return ""

    total_seconds = int(value.total_seconds())

    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    parts = []

    if days > 0:
        parts.append(f"{days}d")

    if hours > 0:
        parts.append(f"{hours}hr")

    if minutes > 0:
        parts.append(f"{minutes}min")

    return " ".join(parts)