"""Chronological Timeline Engine for Bangladesh Legal Cases.

Parses, normalizes, and sequences case events across English and Bengali dates.
Detects temporal anomalies (e.g. actions preceding causal events).
"""

from datetime import date, datetime
import re
from typing import List, Optional
from backend.src.analysis.schemas import TimelineEventItem, TimelineExtractionResult

# Mapping Bengali digits to English
BN_DIGIT_MAP = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

# Mapping Bengali months to numeric month
BN_MONTHS = {
    "জানুয়ারি": 1, "জানুয়ারি": 1, "january": 1, "jan": 1,
    "ফেব্রুয়ারি": 2, "ফেব্রুয়ারি": 2, "february": 2, "feb": 2,
    "মার্চ": 3, "march": 3, "mar": 3,
    "এপ্রিল": 4, "april": 4, "apr": 4,
    "মে": 5, "may": 5,
    "জুন": 6, "june": 6, "jun": 6,
    "জুলাই": 7, "july": 7, "jul": 7,
    "আগস্ট": 8, "august": 8, "aug": 8,
    "সেপ্টেম্বর": 9, "september": 9, "sep": 9, "sept": 9,
    "অক্টোবর": 10, "october": 10, "oct": 10,
    "নভেম্বর": 11, "november": 11, "nov": 11,
    "ডিসেম্বর": 12, "december": 12, "dec": 12,
}


class TimelineEngine:
    """Extracts, normalizes, and detects temporal anomalies in legal event chronologies."""

    @staticmethod
    def normalize_bengali_digits(text: str) -> str:
        """Convert Bengali numerals to standard Western ASCII digits."""
        return text.translate(BN_DIGIT_MAP)

    @classmethod
    def parse_legal_date(cls, raw_date: str) -> Optional[date]:
        """Parse diverse Bangladesh legal date formats in English and Bangla into datetime.date."""
        if not raw_date:
            return None

        clean_text = cls.normalize_bengali_digits(raw_date.strip())

        # Format: YYYY-MM-DD
        iso_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", clean_text)
        if iso_match:
            try:
                y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
                return date(y, m, d)
            except ValueError:
                pass

        # Format: DD/MM/YYYY or DD-MM-YYYY
        dmy_match = re.search(r"(\d{1,2})[/\.-](\d{1,2})[/\.-](\d{4})", clean_text)
        if dmy_match:
            try:
                d, m, y = int(dmy_match.group(1)), int(dmy_match.group(2)), int(dmy_match.group(3))
                return date(y, m, d)
            except ValueError:
                pass

        # Format: DD MonthName YYYY (e.g. 10 January 2023 or ১০ই ফেব্রুয়ারি ২০২৩)
        words = [w.strip() for w in re.split(r"[\s,;]+", clean_text.lower()) if w.strip()]
        day: Optional[int] = None
        month: Optional[int] = None
        year: Optional[int] = None

        for w in words:
            # Check if word is digit
            digits_only = re.sub(r"[^\d]", "", w)
            if digits_only:
                val = int(digits_only)
                if val > 1900 and val < 2100:
                    year = val
                elif val <= 31 and day is None:
                    day = val
            # Check month name
            for m_name, m_num in BN_MONTHS.items():
                if m_name in w:
                    month = m_num
                    break

        if year and month and day:
            try:
                return date(year, month, day)
            except ValueError:
                pass

        return None

    @classmethod
    def sequence_events(cls, events: List[TimelineEventItem]) -> List[TimelineEventItem]:
        """Sort timeline events chronologically and detect temporal anomalies."""
        parsed_entries = []
        for ev in events:
            d = cls.parse_legal_date(ev.event_date) or cls.parse_legal_date(ev.raw_date_text)
            if d:
                ev.event_date = d.isoformat()
            parsed_entries.append((d or date(1970, 1, 1), ev))

        # Sort chronologically
        parsed_entries.sort(key=lambda x: x[0])
        sorted_events = [entry[1] for entry in parsed_entries]

        # Anomaly detection pass
        for i in range(len(sorted_events) - 1):
            curr_ev = sorted_events[i]
            next_ev = sorted_events[i + 1]

            # Example: Dishonour / Notice event cannot occur before Cheque Issuance
            if "dishonour" in curr_ev.title.lower() and "issuance" in next_ev.title.lower():
                next_ev.is_anomaly = True
                next_ev.anomaly_reason = (
                    f"Temporal sequence inversion: Cheque Issuance is dated after Bank Dishonour."
                )

            # Check for sudden multi-decade gaps
            d_curr = cls.parse_legal_date(curr_ev.event_date)
            d_next = cls.parse_legal_date(next_ev.event_date)
            if d_curr and d_next:
                gap_days = (d_next - d_curr).days
                if gap_days < 0:
                    next_ev.is_anomaly = True
                    next_ev.anomaly_reason = f"Event date ({next_ev.event_date}) is chronologically before prior event ({curr_ev.event_date})."

        return sorted_events
