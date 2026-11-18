"""Tests for Chronological Timeline Engine and Date Normalization."""

from datetime import date
from backend.src.analysis.schemas import TimelineEventItem
from backend.src.analysis.timeline import TimelineEngine


def test_bengali_digits_normalization():
    raw = "০১২৩৪৫৬৭৮৯"
    normalized = TimelineEngine.normalize_bengali_digits(raw)
    assert normalized == "0123456789"


def test_parse_legal_date_english_iso():
    d = TimelineEngine.parse_legal_date("2023-01-25")
    assert d == date(2023, 1, 25)


def test_parse_legal_date_english_formatted():
    d = TimelineEngine.parse_legal_date("10 January 2023")
    assert d == date(2023, 1, 10)


def test_parse_legal_date_bengali():
    # ১০ই ফেব্রুয়ারি ২০২৩
    d = TimelineEngine.parse_legal_date("১০ই ফেব্রুয়ারি ২০২৩")
    assert d == date(2023, 2, 10)


def test_timeline_sequencing_and_sorting():
    events = [
        TimelineEventItem(
            event_date="2023-03-20",
            raw_date_text="20 March 2023",
            title="Complaint Filed",
            description="Petition filed in C.R. case",
        ),
        TimelineEventItem(
            event_date="2023-01-10",
            raw_date_text="10 Jan 2023",
            title="Cheque Issuance",
            description="Cheque issued",
        ),
        TimelineEventItem(
            event_date="2023-01-25",
            raw_date_text="25 Jan 2023",
            title="Bank Dishonour",
            description="Cheque returned unpaid",
        ),
    ]

    sequenced = TimelineEngine.sequence_events(events)
    assert len(sequenced) == 3
    assert sequenced[0].title == "Cheque Issuance"
    assert sequenced[1].title == "Bank Dishonour"
    assert sequenced[2].title == "Complaint Filed"


def test_timeline_anomaly_detection():
    # Bank Dishonour dated BEFORE Cheque Issuance is a temporal anomaly
    events = [
        TimelineEventItem(
            event_date="2023-01-10",
            title="Bank Dishonour",
            description="Dishonour memo received",
        ),
        TimelineEventItem(
            event_date="2023-01-25",
            title="Cheque Issuance",
            description="Cheque signed by drawer",
        ),
    ]

    sequenced = TimelineEngine.sequence_events(events)
    # The anomaly detector flags the inverted issuance event
    assert any(e.is_anomaly for e in sequenced)
