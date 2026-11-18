"""Parse raw GSMArena spec strings into numeric 'key specs' and prices."""
from __future__ import annotations

import re
from typing import Optional

Specs = dict[str, dict[str, str]]  # {category: {key: value}}

_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "USD": "USD", "EUR": "EUR",
             "GBP": "GBP", "INR": "INR"}


def _get(specs: Specs, category: str, key: str) -> str:
    return specs.get(category, {}).get(key, "") or ""


def _first_float(pattern: str, text: str) -> Optional[float]:
    m = re.search(pattern, text, re.I)
    return float(m.group(1).replace(",", "")) if m else None


def _first_int(pattern: str, text: str) -> Optional[int]:
    v = _first_float(pattern, text)
    return int(v) if v is not None else None


def parse_key_specs(specs: Specs) -> dict:
    display_type = _get(specs, "Display", "Type")
    memory = _get(specs, "Memory", "Internal")

    ram = [int(x) for x in re.findall(r"(\d+)\s*GB\s*RAM", memory, re.I)]
    storage = []
    for num, unit in re.findall(r"(\d+)\s*(GB|TB)(?!\s*RAM)", memory, re.I):
        storage.append(int(num) * (1024 if unit.upper() == "TB" else 1))

    # Main camera: the first non-video/feature row lists every module, main first.
    cam_text = ""
    for key, value in specs.get("Main Camera", {}).items():
        if key.lower() not in ("features", "video"):
            cam_text = value
            break
    mps = re.findall(r"(\d+(?:\.\d+)?)\s*MP", cam_text, re.I)
    # Collapse repeats caused by sub-lines such as "(wide)... 12 MP (ultrawide)".
    camera_summary = (" + ".join(mps) + " MP") if mps else None

    charging = _get(specs, "Battery", "Charging")
    wired = _first_int(r"(\d+)\s*W\s*wired", charging)
    if wired is None:
        wired = _first_int(r"(\d+)\s*W", charging)

    os_text = _get(specs, "Platform", "OS")
    return {
        "display_size_in": _first_float(r"([\d.]+)\s*inch", _get(specs, "Display", "Size")),
        "display_type": display_type.split(",")[0].strip() or None,
        "resolution": (re.search(r"\d+\s*x\s*\d+", _get(specs, "Display", "Resolution")) or [None])[0],
        "refresh_rate_hz": _first_int(r"(\d+)\s*Hz", display_type),
        "chipset": _get(specs, "Platform", "Chipset") or None,
        "os": os_text.split(",")[0].strip() or None,
        "ram_gb_max": max(ram) if ram else None,
        "storage_gb_max": max(storage) if storage else None,
        "main_camera_mp": float(mps[0]) if mps else None,
        "camera_summary": camera_summary,
        "battery_mah": _first_int(r"(\d{3,5})\s*mAh", _get(specs, "Battery", "Type")),
        "charging_w": wired,
        "weight_g": _first_float(r"([\d.]+)\s*g\b", _get(specs, "Body", "Weight")),
    }


def parse_prices(price_text: str) -> list[tuple[str, float]]:
    """'$ 799.99 / € 659.00' or 'About 400 EUR' -> [('USD', 799.99), ('EUR', 659.0)]"""
    out: list[tuple[str, float]] = []
    for sym, num in re.findall(r"([$€£₹])\s*([\d,]+(?:\.\d+)?)", price_text):
        out.append((_CURRENCY[sym], float(num.replace(",", ""))))
    for num, cur in re.findall(r"([\d,]+(?:\.\d+)?)\s*(USD|EUR|GBP|INR)\b", price_text):
        out.append((_CURRENCY[cur], float(num.replace(",", ""))))
    return out
