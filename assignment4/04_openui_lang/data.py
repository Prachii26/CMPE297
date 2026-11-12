"""The running example: a campus study-room booking dashboard.

Fixed, in-process data -- no database, no network. Every theme carries its
own copy so each theme stays self-contained with its own .venv.
"""

ROOMS = [
    {"id": "LIB-201", "name": "Library 201", "building": "King Library", "capacity": 4,
     "available": True, "next_free": "now"},
    {"id": "LIB-305", "name": "Library 305", "building": "King Library", "capacity": 8,
     "available": False, "next_free": "14:00"},
    {"id": "ENG-112", "name": "Engineering 112", "building": "Engineering", "capacity": 6,
     "available": True, "next_free": "now"},
    {"id": "ENG-240", "name": "Engineering 240", "building": "Engineering", "capacity": 12,
     "available": False, "next_free": "16:30"},
    {"id": "SU-018", "name": "Student Union 018", "building": "Student Union", "capacity": 2,
     "available": True, "next_free": "now"},
    {"id": "SCI-404", "name": "Science 404", "building": "Science", "capacity": 10,
     "available": False, "next_free": "15:00"},
]

# share of rooms booked, by hour of the day
OCCUPANCY = [
    {"hour": "08", "pct": 20}, {"hour": "10", "pct": 55}, {"hour": "12", "pct": 85},
    {"hour": "14", "pct": 90}, {"hour": "16", "pct": 70}, {"hour": "18", "pct": 45},
    {"hour": "20", "pct": 25},
]

SLOTS = ["13:00-14:00", "14:00-15:00", "15:00-16:00", "16:00-17:00"]


def metrics() -> list[dict]:
    free = sum(r["available"] for r in ROOMS)
    return [
        {"label": "Rooms free now", "value": f"{free} / {len(ROOMS)}"},
        {"label": "Peak occupancy", "value": f"{max(o['pct'] for o in OCCUPANCY)}%"},
        {"label": "Bookings today", "value": "37"},
    ]


def book(room_id: str, slot: str) -> dict:
    room = next((r for r in ROOMS if r["id"] == room_id), None)
    if room is None:
        return {"ok": False, "message": f"unknown room {room_id}"}
    if slot not in SLOTS:
        return {"ok": False, "message": f"unknown slot {slot}"}
    return {"ok": True, "message": f"Booked {room['name']} for {slot}.",
            "booking_id": f"BK-{room_id}-{slot[:2]}"}
