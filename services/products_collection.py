"""Small, reusable validation helpers for Products module items."""
from __future__ import annotations
from typing import Any
from urllib.parse import urlparse

class ProductValidationError(ValueError):
    """Raised when a Products module item does not meet its minimal contract."""

def add_product(items: list[dict[str, Any]] | None, name: str, description: str = "", link: str = "") -> list[dict[str, str]]:
    """Return a new item collection without mutating previously saved products."""
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ProductValidationError("Название продукта обязательно. Напиши его, пожалуйста.")
    normalized_link = str(link or "").strip()
    if normalized_link:
        parsed = urlparse(normalized_link)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ProductValidationError("Укажи корректную ссылку с http:// или https://, либо отправь «-».")
    product = {"name": normalized_name, "description": str(description or "").strip(), "link": normalized_link}
    return [dict(item) for item in (items or [])] + [product]
