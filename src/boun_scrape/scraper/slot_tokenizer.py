"""Slot tokenizer: day lookahead, hour algebraic partition, and room replication/padding."""

from boun_scrape.domain.models import CourseSlot

TWO_LETTER_DAYS: frozenset[str] = frozenset({"Th", "St", "Su"})


def parse_days(day_str: str | None) -> list[str]:
    """Parse days from schedule code using 2-character lookahead.

    Handles two-character day codes (Th, St, Su), single-character codes (M, T, W, F),
    and TBA designations.
    """
    if not day_str:
        return []

    cleaned = day_str.strip()
    if not cleaned:
        return []

    if cleaned == "TBA":
        return ["TBA"]

    # Remove inner whitespace if present (e.g. "M W F")
    cleaned = "".join(cleaned.split())
    if cleaned == "TBA":
        return ["TBA"]

    days: list[str] = []
    i = 0
    length = len(cleaned)
    while i < length:
        if i + 1 < length and cleaned[i : i + 2] in TWO_LETTER_DAYS:
            days.append(cleaned[i : i + 2])
            i += 2
        else:
            days.append(cleaned[i])
            i += 1
    return days


def parse_hours(hour_str: str | None, num_slots: int) -> list[str]:
    """Parse class hour periods from concatenated or space-separated strings.

    Solves the 2-digit hour partition algebraically for hours 10-14 when concatenated
    (e.g., '8910' for 3 slots -> ['8', '9', '10'], '101112' for 3 slots -> ['10', '11', '12']).
    """
    if num_slots <= 0:
        return []

    if not hour_str:
        return [""] * num_slots

    cleaned = hour_str.strip()
    if not cleaned:
        return [""] * num_slots

    if cleaned == "TBA":
        return ["TBA"] * num_slots

    tokens = cleaned.split()
    if len(tokens) == num_slots:
        return tokens

    raw = "".join(tokens)
    if len(raw) == num_slots:
        return list(raw)

    num_2_digit = len(raw) - num_slots
    if num_2_digit <= 0:
        chars = list(raw)
        if len(chars) < num_slots:
            chars.extend([""] * (num_slots - len(chars)))
        return chars[:num_slots]

    # Periods are always listed in ascending order and only periods 10-14 are
    # two digits, so every two-digit period trails every single-digit one:
    # take the leading single-digit periods first, then chunk the remainder
    # into two-digit periods. (A purely greedy left-to-right scan for '1'
    # misparses cases like '110' for 2 slots — period 1 followed by period 10 —
    # as ['11', '0'] instead of ['1', '10'].)
    num_single_digit = num_slots - num_2_digit
    res: list[str] = list(raw[:num_single_digit])
    remainder = raw[num_single_digit:]
    res.extend(remainder[i : i + 2] for i in range(0, len(remainder), 2))

    if len(res) < num_slots:
        res.extend([""] * (num_slots - len(res)))
    return res[:num_slots]


def parse_rooms(room_raw: str | None, num_slots: int) -> list[str]:
    """Parse classroom codes, handling delimiters, HTML entities, replication, and padding.

    - Single room with multiple slots is replicated across all slots.
    - Missing rooms are padded with empty strings up to num_slots.
    - Multiple rooms delimited by '|' or whitespace are assigned positionally.
    """
    if num_slots <= 0:
        return []

    if not room_raw:
        return [""] * num_slots

    cleaned = room_raw.replace("&nbsp;", " ").strip()
    if not cleaned:
        return [""] * num_slots

    if cleaned == "TBA":
        return ["TBA"] * num_slots

    # If pipes or newlines exist, preserve empty intermediate segments
    if "|" in cleaned or "\n" in cleaned or "\r" in cleaned:
        raw_parts = cleaned.replace("\r", "|").replace("\n", "|").split("|")
        parts = [p.strip() for p in raw_parts]
        if not any(parts):
            return [""] * num_slots
    else:
        parts = [cleaned]

    if len(parts) == 1 and num_slots > 1 and parts[0]:
        return parts * num_slots

    if len(parts) < num_slots:
        return parts + [""] * (num_slots - len(parts))

    return parts[:num_slots]


def build_slots(
    *,
    day_str: str | None,
    hour_str: str | None,
    room_raw: str | None,
    slot_title: str | None = None,
    instructor: str | None = None,
) -> list[CourseSlot]:
    """Tokenize day, hour, and room strings into CourseSlot domain models."""
    days = parse_days(day_str)
    if not days:
        if (day_str and day_str.strip() == "TBA") or (
            hour_str and hour_str.strip() == "TBA"
        ):
            days = ["TBA"]
        else:
            return []

    num_slots = len(days)
    hours = parse_hours(hour_str, num_slots)
    rooms = parse_rooms(room_raw, num_slots)

    return [
        CourseSlot(
            day=d,
            hour=h,
            room=r,
            slot_title=slot_title,
            instructor=instructor,
        )
        for d, h, r in zip(days, hours, rooms)
    ]
