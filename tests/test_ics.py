import pandas as pd
from lab_293t_scheduler_app import build_ics


def test_build_ics_structure_and_event_count():
    df = pd.DataFrame(
        [
            {"Passage": "P12", "Day": "Monday", "Date": "2026-01-05", "IsWeekend": "Weekday", "AssignedGroup": "Group A", "Person": "Alice A"},
            {"Passage": "P13", "Day": "Wednesday", "Date": "2026-01-07", "IsWeekend": "Weekday", "AssignedGroup": "Group A", "Person": "Alice A"},
        ]
    )
    ics = build_ics(df, event_hour=9, duration_minutes=60)

    assert ics.startswith("BEGIN:VCALENDAR")
    assert ics.strip().endswith("END:VCALENDAR")
    assert ics.count("BEGIN:VEVENT") == len(df)
    assert ics.count("END:VEVENT") == len(df)

    assert "DTSTART:20260105T090000" in ics
    assert "DTEND:20260105T100000" in ics
    assert "SUMMARY:293T Split – Alice A (Group A)" in ics
    assert "UID:293t-2026-01-05-AliceA@scheduler" in ics
