"""Thirty synthetic VoltLoop bugs. Fixed data, so tests and demos are stable."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from .db import SCHEMA

# (title, description, component, severity, status, reporter, assignee, age_days)
BUGS: list[tuple[str, str, str, str, str, str, str | None, int]] = [
    ("Ride unlock charges rider twice on retry",
     "Tapping unlock a second time after a slow NFC read creates two payment intents. Rider is billed twice for one ride. Seen on iOS 17 and Android 14.",
     "payments", "S1", "open", "nina.rao", None, 2),
    ("Refund webhook signature check rejects valid Stripe calls",
     "The verifier compares the raw body after JSON re-serialisation, so whitespace differences break the HMAC. All refunds silently stay pending.",
     "payments", "S1", "in_progress", "omar.diaz", "lee.park", 5),
    ("Session token not rotated after password reset",
     "Old bearer tokens stay valid for their full 24h TTL after a reset, so a stolen token survives the mitigation.",
     "auth", "S1", "open", "security-scan", None, 1),
    ("Scooter firmware brake telemetry drops below 15 percent battery",
     "Below 15 percent the MCU drops brake-wear frames to save power. Fleet ops lose brake data exactly when scooters most need servicing.",
     "iot-firmware", "S1", "open", "fleet.ops", "yuki.sato", 9),
    ("Dispatch API returns scooters already reserved by another rider",
     "The reservation lock is advisory rather than transactional. Two riders can reserve the same scooter inside a 400ms window.",
     "dispatch-api", "S1", "blocked", "priya.n", "sam.ou", 12),
    ("Docking station reports slot free while scooter is physically latched",
     "Hall-effect sensor debounce is 50ms but mechanical bounce lasts about 90ms. The station publishes slot_free and the next rider cannot dock.",
     "docking-station", "S2", "open", "field.tech", None, 4),
    ("Promo code stacking bypasses the per-rider cap",
     "Two promo codes applied in one request each read the pre-decrement counter, so a rider can stack beyond the one-per-month cap.",
     "billing-batch", "S2", "open", "finance.audit", None, 7),
    ("Map shows scooters at origin coordinates when GPS fix is stale",
     "Null island cluster. We render last_known_location without checking the fix timestamp, so riders walk to a scooter that is not there.",
     "maps", "S2", "open", "rider.support", "ana.ruiz", 3),
    ("OAuth callback drops deep link on cold app start",
     "If the app process was killed, the post-login deep link is lost and the rider lands on the home screen instead of the ride they opened.",
     "auth", "S2", "in_progress", "qa.team", "lee.park", 14),
    ("Mobile app crashes on ride summary for a zero-distance ride",
     "Division by zero computing average speed when a ride is cancelled under 5 metres. Null pointer in RideSummaryViewModel.",
     "mobile-app", "S2", "open", "crashlytics", None, 2),
    ("Nightly billing batch double-counts rides crossing midnight UTC",
     "The batch window is inclusive on both ends, so a ride spanning midnight lands in two invoices.",
     "billing-batch", "S2", "open", "finance.audit", None, 11),
    ("Dispatch rebalancing ignores the scooter brake-wear flag",
     "The rebalancer optimises purely on demand heat, so scooters flagged for brake service get redeployed into high-traffic zones.",
     "dispatch-api", "S2", "open", "fleet.ops", None, 6),
    ("Firmware OTA retries forever on a 413 response",
     "A too-large manifest returns 413 and the updater retries every 30s indefinitely, draining the scooter battery overnight.",
     "iot-firmware", "S2", "blocked", "yuki.sato", "yuki.sato", 18),
    ("Payment method deletion leaves an orphaned mandate",
     "Deleting a card removes our row but never revokes the SEPA mandate upstream, so we can still be charged fees.",
     "payments", "S2", "open", "omar.diaz", None, 8),
    ("Rate limiter keyed on IP blocks shared-NAT campus riders",
     "An entire university campus behind one NAT hits the 60 req/min cap, locking out legitimate riders at class change.",
     "auth", "S3", "open", "rider.support", None, 16),
    ("Scooter search radius ignores the unit preference",
     "Radius is always treated as metres, so riders with imperial units set a 2-mile radius and get a 2-metre search.",
     "maps", "S3", "open", "qa.team", "ana.ruiz", 5),
    ("Docking station LED stuck amber after a successful dock",
     "The LED state machine has no transition from amber back to green once a dock completes, so stations look broken to riders.",
     "docking-station", "S3", "open", "field.tech", None, 21),
    ("Ride history pagination repeats the last item",
     "The cursor is inclusive on both ends, so every page after the first begins with the final ride of the previous page.",
     "mobile-app", "S3", "open", "nina.rao", None, 13),
    ("Invoice PDF renders rider name in the wrong character set",
     "Non-Latin names render as boxes because the PDF font subset only embeds Latin-1 glyphs.",
     "billing-batch", "S3", "open", "rider.support", None, 24),
    ("Dispatch API returns 500 when a zone polygon self-intersects",
     "Operator-drawn zones are not validated, and a bowtie polygon crashes the point-in-polygon check.",
     "dispatch-api", "S3", "open", "sam.ou", "sam.ou", 10),
    ("Push notification sent in English regardless of locale",
     "The notification service reads locale from the request header rather than the rider profile, so backend-triggered pushes default to English.",
     "mobile-app", "S3", "open", "intl.team", None, 19),
    ("Firmware clock drifts 4s per day without NTP sync",
     "RTC drift is uncorrected between OTA windows, so ride start timestamps disagree with server time by seconds.",
     "iot-firmware", "S3", "open", "yuki.sato", None, 27),
    ("Map tile cache never evicts and app storage grows unbounded",
     "There is no max size on the tile cache. Heavy riders report multi-GB app storage after a few months.",
     "maps", "S3", "in_progress", "crashlytics", "ana.ruiz", 15),
    ("Password rules reject valid long passphrases",
     "A 64-character limit is enforced client side only and the error message does not say why the passphrase was rejected.",
     "auth", "S4", "open", "rider.support", None, 30),
    ("Receipt email subject line has a trailing space",
     "Cosmetic. Template interpolation leaves a trailing space before the closing quote.",
     "billing-batch", "S4", "open", "marketing", None, 22),
    ("Docking station admin page column sort is case sensitive",
     "Sorting station names puts lowercase entries after all uppercase ones.",
     "docking-station", "S4", "open", "field.tech", None, 28),
    ("Settings screen shows app version without the build number",
     "Support cannot tell which build a rider is on, which slows down crash triage.",
     "mobile-app", "S4", "open", "rider.support", None, 25),
    ("Scooter marker icon is 2px off centre on the map pin",
     "The anchor point uses the icon top-left instead of bottom-centre, so the pin tip misses the actual location slightly.",
     "maps", "S4", "resolved", "design.qa", "ana.ruiz", 26),
    ("Dispatch dashboard tooltip truncates long zone names",
     "Zone names over 24 characters are cut without an ellipsis, so operators cannot tell similar zones apart.",
     "dispatch-api", "S4", "closed", "fleet.ops", "sam.ou", 29),
    ("Firmware debug log prints the full rider UUID",
     "Debug build only, but rider UUIDs in serial logs are more personal data than field techs need.",
     "iot-firmware", "S4", "resolved", "security-scan", "yuki.sato", 20),
]


def seed(conn: sqlite3.Connection, force: bool = False) -> int:
    """Create the schema and insert the fixture bugs. Returns rows inserted."""
    conn.executescript(SCHEMA)
    if force:
        conn.executescript(
            "DELETE FROM status_history; DELETE FROM comments; DELETE FROM bugs;"
        )
    existing = conn.execute("SELECT COUNT(*) FROM bugs").fetchone()[0]
    if existing and not force:
        return 0

    now = datetime.now(timezone.utc)
    rows = []
    for i, (title, desc, comp, sev, status, reporter, assignee, age) in enumerate(
        BUGS, start=1
    ):
        created = now - timedelta(days=age)
        # Updated deterministically somewhere between creation and now.
        updated = created + timedelta(hours=(i * 7) % max(age * 24, 1))
        rows.append((
            f"VLT-{100 + i}", title, desc, comp, sev, status, reporter, assignee,
            created.isoformat(timespec="seconds"),
            min(updated, now).isoformat(timespec="seconds"),
        ))
    conn.executemany(
        "INSERT INTO bugs (id,title,description,component,severity,status,"
        "reporter,assignee,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)
