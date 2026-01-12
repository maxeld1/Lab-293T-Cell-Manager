import pandas as pd
import pytest

from lab_293t_scheduler_app import ScheduleParams, generate_293t_schedule, PASSAGE_CYCLE


def params_base(**overrides):
    base = ScheduleParams(
        group_a=["A1", "A2"],
        group_b=["B1", "B2"],
        start_date=pd.Timestamp("2026-01-04"),  # Sunday
        end_date=pd.Timestamp("2026-01-18"),
        num_events=None,
        start_roles=("weekday", "weekend"),
        interval_hours=48,
        skip_dates=[],
        start_passage_label="P25, Thaw P11",
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_reject_both_end_date_and_num_events():
    p = params_base(end_date=pd.Timestamp("2026-01-10"), num_events=5)
    with pytest.raises(AssertionError):
        generate_293t_schedule(p)


def test_reject_neither_end_date_nor_num_events():
    p = params_base(end_date=None, num_events=None)
    with pytest.raises(AssertionError):
        generate_293t_schedule(p)


def test_reject_empty_group_a():
    p = params_base()
    p.group_a = []
    with pytest.raises(ValueError, match="Group A is empty"):
        generate_293t_schedule(p)


def test_reject_empty_group_b():
    p = params_base()
    p.group_b = []
    with pytest.raises(ValueError, match="Group B is empty"):
        generate_293t_schedule(p)


def test_reject_invalid_start_roles_values():
    p = params_base(start_roles=("weekday", "weekdayish"))
    with pytest.raises(ValueError):
        generate_293t_schedule(p)


def test_reject_same_start_roles():
    p = params_base(start_roles=("weekday", "weekday"))
    with pytest.raises(ValueError, match="same role"):
        generate_293t_schedule(p)


def test_reject_unknown_start_passage_label():
    p = params_base(start_passage_label="P999")
    with pytest.raises(ValueError, match="Unknown start passage"):
        generate_293t_schedule(p)


def test_columns_present_and_values_reasonable():
    df = generate_293t_schedule(params_base())
    assert set(df.columns) == {"Passage", "Day", "Date", "IsWeekend", "AssignedGroup", "Person"}
    assert df["Date"].str.match(r"\d{4}-\d{2}-\d{2}").all()
    assert df["IsWeekend"].isin(["Weekend", "Weekday"]).all()
    assert df["AssignedGroup"].isin(["Group A", "Group B"]).all()


def test_passage_cycle_starts_at_label_and_wraps():
    p = params_base(num_events=20, end_date=None, start_passage_label="P12")
    df = generate_293t_schedule(p)

    expected = []
    idx = PASSAGE_CYCLE.index("P12")
    for _ in range(len(df)):
        expected.append(PASSAGE_CYCLE[idx])
        idx = (idx + 1) % len(PASSAGE_CYCLE)

    assert df["Passage"].tolist() == expected


def test_skip_dates_excluded_and_event_count_preserved():
    p = params_base(num_events=6, end_date=None, skip_dates=[pd.Timestamp("2026-01-08")])
    df = generate_293t_schedule(p)
    assert "2026-01-08" not in set(df["Date"])
    assert len(df) == 6


def test_week_bucket_rule_weekdays_share_same_person_within_week():
    p = params_base(num_events=14, end_date=None)
    df = generate_293t_schedule(p)

    df_dt = pd.to_datetime(df["Date"])
    df = df.assign(_dt=df_dt)

    def week_start_sunday(ts):
        days_since_sun = (ts.weekday() + 1) % 7
        return (ts - pd.Timedelta(days=days_since_sun)).normalize()

    df = df.assign(_wk=df["_dt"].apply(week_start_sunday))

    for wk, sub in df.groupby("_wk"):
        weekdays = sub[sub["Day"].isin(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])]
        if len(weekdays) > 1:
            assert weekdays["Person"].nunique() == 1


def test_role_flip_only_after_both_groups_wrap():
    # 1-person groups => every consumption wraps immediately
    p = ScheduleParams(
        group_a=["A1"],
        group_b=["B1"],
        start_date=pd.Timestamp("2026-01-04"),
        num_events=10,
        end_date=None,
        start_roles=("weekday", "weekend"),
        interval_hours=48,
        skip_dates=[],
        start_passage_label="P25, Thaw P11",
    )
    df = generate_293t_schedule(p)

    first_weekday = df[df["IsWeekend"] == "Weekday"].iloc[0]["AssignedGroup"]
    first_weekend = df[df["IsWeekend"] == "Weekend"].iloc[0]["AssignedGroup"]
    assert first_weekday == "Group A"
    assert first_weekend == "Group B"

    # Later, weekdays should flip at least once
    assert "Group B" in df[df["IsWeekend"] == "Weekday"]["AssignedGroup"].tolist()
