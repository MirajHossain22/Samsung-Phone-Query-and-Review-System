"""Offline SAMPLE dataset (12 Galaxy S-series flagships) in the same shape the scraper produces.

Purpose: let the chatbot / agents / API be demoed and tested without network access.
Values were compiled from public launch spec sheets and are NOT live GSMArena data -
run `python -m samsung_assistant.scraper` to replace them with scraped data.
Prices are US launch prices (USD) of the base storage model.

Run:  python -m samsung_assistant.seed
"""
from __future__ import annotations

from .db import Database
from .repository import PhoneRepository

# name, announced, size(in), display type, resolution, chipset, ram/storage string,
# main camera string, selfie, battery mAh, charging text, weight g, price USD, OS
_ROWS = [
    ("Samsung Galaxy S21", "2021, January 14", 6.2, "Dynamic AMOLED 2X, 120Hz, HDR10+", "1080 x 2400 pixels",
     "Exynos 2100 (5 nm) / Snapdragon 888 5G (5 nm)", "128GB 8GB RAM, 256GB 8GB RAM",
     "12 MP (wide), 12 MP (ultrawide), 64 MP (telephoto)", "10 MP", 4000, "25W wired, 15W wireless", 169, 799,
     "Android 11, up to Android 14, One UI 6.1"),
    ("Samsung Galaxy S21+", "2021, January 14", 6.7, "Dynamic AMOLED 2X, 120Hz, HDR10+", "1080 x 2400 pixels",
     "Exynos 2100 (5 nm) / Snapdragon 888 5G (5 nm)", "128GB 8GB RAM, 256GB 8GB RAM",
     "12 MP (wide), 12 MP (ultrawide), 64 MP (telephoto)", "10 MP", 4800, "25W wired, 15W wireless", 200, 999,
     "Android 11, up to Android 14, One UI 6.1"),
    ("Samsung Galaxy S21 Ultra", "2021, January 14", 6.8, "Dynamic AMOLED 2X, 120Hz, HDR10+", "1440 x 3200 pixels",
     "Exynos 2100 (5 nm) / Snapdragon 888 5G (5 nm)", "128GB 12GB RAM, 256GB 12GB RAM, 512GB 16GB RAM",
     "108 MP (wide), 12 MP (ultrawide), 10 MP (telephoto), 10 MP (periscope telephoto)", "40 MP", 5000,
     "25W wired, 15W wireless", 227, 1199, "Android 11, up to Android 14, One UI 6.1"),
    ("Samsung Galaxy S22", "2022, February 09", 6.1, "Dynamic AMOLED 2X, 120Hz, HDR10+", "1080 x 2340 pixels",
     "Exynos 2200 (4 nm) / Snapdragon 8 Gen 1 (4 nm)", "128GB 8GB RAM, 256GB 8GB RAM",
     "50 MP (wide), 12 MP (ultrawide), 10 MP (telephoto)", "10 MP", 3700, "25W wired, 15W wireless", 167, 799,
     "Android 12, up to Android 15, One UI 7"),
    ("Samsung Galaxy S22+", "2022, February 09", 6.6, "Dynamic AMOLED 2X, 120Hz, HDR10+", "1080 x 2340 pixels",
     "Exynos 2200 (4 nm) / Snapdragon 8 Gen 1 (4 nm)", "128GB 8GB RAM, 256GB 8GB RAM",
     "50 MP (wide), 12 MP (ultrawide), 10 MP (telephoto)", "10 MP", 4500, "45W wired, 15W wireless", 196, 999,
     "Android 12, up to Android 15, One UI 7"),
    ("Samsung Galaxy S22 Ultra", "2022, February 09", 6.8, "Dynamic AMOLED 2X, 120Hz, HDR10+", "1440 x 3088 pixels",
     "Exynos 2200 (4 nm) / Snapdragon 8 Gen 1 (4 nm)", "128GB 8GB RAM, 256GB 12GB RAM, 512GB 12GB RAM, 1TB 12GB RAM",
     "108 MP (wide), 12 MP (ultrawide), 10 MP (telephoto), 10 MP (periscope telephoto)", "40 MP", 5000,
     "45W wired, 15W wireless", 229, 1199, "Android 12, up to Android 15, One UI 7"),
    ("Samsung Galaxy S23", "2023, February 01", 6.1, "Dynamic AMOLED 2X, 120Hz, HDR10+", "1080 x 2340 pixels",
     "Snapdragon 8 Gen 2 (4 nm)", "128GB 8GB RAM, 256GB 8GB RAM, 512GB 8GB RAM",
     "50 MP (wide), 12 MP (ultrawide), 10 MP (telephoto)", "12 MP", 3900, "25W wired, 15W wireless", 168, 799,
     "Android 13, up to Android 16, One UI 8"),
    ("Samsung Galaxy S23+", "2023, February 01", 6.6, "Dynamic AMOLED 2X, 120Hz, HDR10+", "1080 x 2340 pixels",
     "Snapdragon 8 Gen 2 (4 nm)", "256GB 8GB RAM, 512GB 8GB RAM",
     "50 MP (wide), 12 MP (ultrawide), 10 MP (telephoto)", "12 MP", 4700, "45W wired, 15W wireless", 195, 999,
     "Android 13, up to Android 16, One UI 8"),
    ("Samsung Galaxy S23 Ultra", "2023, February 01", 6.8, "Dynamic AMOLED 2X, 120Hz, HDR10+", "1440 x 3088 pixels",
     "Snapdragon 8 Gen 2 (4 nm)", "256GB 8GB RAM, 512GB 12GB RAM, 1TB 12GB RAM",
     "200 MP (wide), 12 MP (ultrawide), 10 MP (telephoto), 10 MP (periscope telephoto)", "12 MP", 5000,
     "45W wired, 15W wireless", 233, 1199, "Android 13, up to Android 16, One UI 8"),
    ("Samsung Galaxy S24", "2024, January 17", 6.2, "Dynamic LTPO AMOLED 2X, 120Hz, HDR10+", "1080 x 2340 pixels",
     "Exynos 2400 (4 nm) / Snapdragon 8 Gen 3 (4 nm)", "128GB 8GB RAM, 256GB 8GB RAM, 512GB 8GB RAM",
     "50 MP (wide), 12 MP (ultrawide), 10 MP (telephoto)", "12 MP", 4000, "25W wired, 15W wireless", 167, 799,
     "Android 14, up to 7 major Android upgrades, One UI 6.1"),
    ("Samsung Galaxy S24+", "2024, January 17", 6.7, "Dynamic LTPO AMOLED 2X, 120Hz, HDR10+", "1440 x 3120 pixels",
     "Exynos 2400 (4 nm) / Snapdragon 8 Gen 3 (4 nm)", "256GB 12GB RAM, 512GB 12GB RAM",
     "50 MP (wide), 12 MP (ultrawide), 10 MP (telephoto)", "12 MP", 4900, "45W wired, 15W wireless", 196, 999,
     "Android 14, up to 7 major Android upgrades, One UI 6.1"),
    ("Samsung Galaxy S24 Ultra", "2024, January 17", 6.8, "Dynamic LTPO AMOLED 2X, 120Hz, HDR10+", "1440 x 3120 pixels",
     "Snapdragon 8 Gen 3 (4 nm)", "256GB 12GB RAM, 512GB 12GB RAM, 1TB 12GB RAM",
     "200 MP (wide), 12 MP (ultrawide), 50 MP (periscope telephoto), 10 MP (telephoto)", "12 MP", 5000,
     "45W wired, 15W wireless", 232, 1299, "Android 14, up to 7 major Android upgrades, One UI 6.1"),
]


def build_records() -> list[dict]:
    records = []
    for (name, ann, size, dtype, res, chip, mem, cam, selfie, mah, charge, grams, usd, os_) in _ROWS:
        records.append({
            "name": name, "url": None, "image_url": None, "announced": ann,
            "specs": {
                "Launch": {"Announced": ann},
                "Body": {"Weight": f"{grams} g"},
                "Display": {"Type": dtype, "Size": f"{size} inches", "Resolution": res},
                "Platform": {"OS": os_, "Chipset": chip},
                "Memory": {"Internal": mem},
                "Main Camera": {"Triple" if cam.count("MP") == 3 else "Quad": cam},
                "Selfie camera": {"Single": selfie},
                "Battery": {"Type": f"Li-Ion {mah} mAh", "Charging": charge},
                "Misc": {"Price": f"$ {usd}.99"},
            },
        })
    return records


def main() -> None:
    db = Database()
    db.init_schema()
    repo = PhoneRepository(db)
    for rec in build_records():
        repo.upsert_phone(rec)
    print(f"Seeded {repo.count()} phones (sample data - run the scraper for live GSMArena data).")


if __name__ == "__main__":
    main()
