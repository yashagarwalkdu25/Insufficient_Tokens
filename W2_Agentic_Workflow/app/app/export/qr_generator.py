"""QR code generation with TripSaathi brand color."""
from __future__ import annotations

import io
from typing import Any

try:
    import qrcode
    from qrcode.image.pil import PilImage
    HAS_QR = True
except ImportError:
    HAS_QR = False

_BRAND_TEAL = "#1A5653"


def generate_qr_bytes(
    data: str,
    size: int = 200,
    fill_color: str = _BRAND_TEAL,
    back_color: str = "white",
) -> bytes:
    if not HAS_QR:
        return b""
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fill_color, back_color=back_color, image_factory=PilImage)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_qr_image(data: str) -> Any:
    if not HAS_QR:
        return None
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color=_BRAND_TEAL, back_color="white", image_factory=PilImage)


def generate_booking_qr(url: str) -> bytes:
    return generate_qr_bytes(url, size=150)


def generate_trip_qr(trip_id: str, base_url: str = "http://localhost:8501") -> bytes:
    url = f"{base_url.rstrip('/')}/?id={trip_id}"
    return generate_qr_bytes(url, size=200)
