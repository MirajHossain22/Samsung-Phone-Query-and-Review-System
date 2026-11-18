"""Read/write access to phones, specs and prices."""
from __future__ import annotations

from typing import Optional

from .db import Database
from .normalize import parse_key_specs, parse_prices

KEY_COLS = ["display_size_in", "display_type", "resolution", "refresh_rate_hz", "chipset", "os",
            "ram_gb_max", "storage_gb_max", "main_camera_mp", "camera_summary", "battery_mah",
            "charging_w", "weight_g"]


class PhoneRepository:
    def __init__(self, db: Database):
        self.db = db

    # ---------------------------------------------------------------- write
    def upsert_phone(self, record: dict) -> int:
        """record = {name, url, image_url, announced, specs: {cat: {key: val}}}"""
        with self.db.transaction():
            return self._upsert_phone(record)

    def _upsert_phone(self, record: dict) -> int:
        pid = self.db.insert_returning_id(
            "INSERT INTO phones (name, brand, url, image_url, announced) VALUES (?, 'Samsung', ?, ?, ?) "
            "ON CONFLICT (name) DO UPDATE SET url = excluded.url, image_url = excluded.image_url, "
            "announced = excluded.announced",
            (record["name"], record.get("url"), record.get("image_url"), record.get("announced")),
        )
        self.db.execute("DELETE FROM specifications WHERE phone_id = ?", (pid,))
        for cat, items in record["specs"].items():
            for key, val in items.items():
                self.db.execute(
                    "INSERT INTO specifications (phone_id, category, spec_key, spec_value) VALUES (?, ?, ?, ?)",
                    (pid, cat, key, val),
                )

        ks = parse_key_specs(record["specs"])
        self.db.execute("DELETE FROM key_specs WHERE phone_id = ?", (pid,))
        self.db.execute(
            f"INSERT INTO key_specs (phone_id, {', '.join(KEY_COLS)}) VALUES (?, {', '.join('?' * len(KEY_COLS))})",
            (pid, *[ks[c] for c in KEY_COLS]),
        )

        self.db.execute("DELETE FROM prices WHERE phone_id = ?", (pid,))
        price_text = record["specs"].get("Misc", {}).get("Price", "")
        for cur, amount in parse_prices(price_text):
            self.db.execute(
                "INSERT INTO prices (phone_id, currency, amount, note) VALUES (?, ?, ?, 'GSMArena Misc/Price') "
                "ON CONFLICT (phone_id, currency, note) DO UPDATE SET amount = excluded.amount",
                (pid, cur, amount),
            )
        return pid

    # ----------------------------------------------------------------- read
    def list_phones(self) -> list[dict]:
        return self.db.query(
            "SELECT p.id, p.name, p.announced, p.url, k.display_size_in, k.chipset, k.main_camera_mp, "
            "k.battery_mah, k.ram_gb_max, k.storage_gb_max, k.charging_w, k.weight_g "
            "FROM phones p LEFT JOIN key_specs k ON k.phone_id = p.id ORDER BY p.name"
        )

    def get_phone(self, name_or_id) -> Optional[dict]:
        """Return the full phone record (key specs, raw specs, prices) or None."""
        if isinstance(name_or_id, int) or str(name_or_id).isdigit():
            rows = self.db.query("SELECT * FROM phones WHERE id = ?", (int(name_or_id),))
        else:
            rows = self.db.query("SELECT * FROM phones WHERE LOWER(name) = LOWER(?)", (str(name_or_id),))
            if not rows:
                rows = self.db.query("SELECT * FROM phones WHERE LOWER(name) LIKE ?",
                                     (f"%{str(name_or_id).lower()}%",))
        if not rows:
            return None
        phone = rows[0]
        pid = phone["id"]
        specs: dict[str, dict[str, str]] = {}
        for r in self.db.query(
            "SELECT category, spec_key, spec_value FROM specifications WHERE phone_id = ? ORDER BY id", (pid,)
        ):
            specs.setdefault(r["category"], {})[r["spec_key"]] = r["spec_value"]
        key = (self.db.query("SELECT * FROM key_specs WHERE phone_id = ?", (pid,)) or [{}])[0]
        key.pop("phone_id", None)
        prices = self.db.query("SELECT currency, amount, note FROM prices WHERE phone_id = ?", (pid,))
        return {**phone, "key_specs": key, "specs": specs, "prices": prices}

    def all_phones(self) -> list[dict]:
        return [self.get_phone(p["id"]) for p in self.list_phones()]

    def count(self) -> int:
        return self.db.query("SELECT COUNT(*) AS n FROM phones")[0]["n"]
