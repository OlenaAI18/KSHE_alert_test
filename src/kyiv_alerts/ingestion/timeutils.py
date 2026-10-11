"""Explicit Europe/Kyiv localization without guessing DST folds or gaps."""
from datetime import datetime, timezone
import re
from zoneinfo import ZoneInfo
from importlib.resources import files

# Use the declared tzdata package on every platform, not a varying OS database.
with files('tzdata.zoneinfo').joinpath('Europe', 'Kyiv').open('rb') as stream:
    KYIV = ZoneInfo.from_file(stream, key='Europe/Kyiv')
UTC = timezone.utc


def null(value):
    """Normalize only native null and the source's literal null sentinel."""
    return None if value is None or value == 'null' else value


def parse_time(value):
    """Return (UTC datetime or None, status); preserve input separately."""
    value = null(value)
    if value is None or value == '':
        return None, 'missing'
    if not isinstance(value, str):
        return None, 'invalid'
    try:
        try:
            local = datetime.fromisoformat(value)
        except ValueError:
            offset_match = re.fullmatch(r'(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}) UTC([+-]\d{2}:\d{2})', value)
            if offset_match:
                local = datetime.strptime(' '.join(offset_match.groups()), '%d.%m.%Y %H:%M:%S %z')
            else:
                local = datetime.strptime(value, '%d.%m.%Y %H:%M:%S')
        if local.tzinfo is not None:
            return local.astimezone(UTC), 'valid_explicit_offset'
        candidates = {
            local.replace(tzinfo=KYIV, fold=fold).astimezone(UTC)
            for fold in (0, 1)
            if local.replace(tzinfo=KYIV, fold=fold).astimezone(UTC)
            .astimezone(KYIV).replace(tzinfo=None) == local
        }
        if len(candidates) == 0:
            return None, 'nonexistent'
        if len(candidates) == 2:
            return None, 'ambiguous'
        return candidates.pop(), 'valid'
    except (ValueError, OverflowError):
        return None, 'invalid'


def valid_status(status):
    return status.startswith('valid')


def parse_telegram_time(value):
    """Validated H2 for this fixed-+02:00 HTML export; original title stays intact.

    Task 002.1's 28 reviewed examples establish that these displayed clocks are
    Europe/Kyiv wall times. Generic ISO offsets and other export formats retain
    parse_time semantics. Never use the fixed suffix to resolve a Kyiv DST fold.
    """
    if isinstance(value, str):
        match = re.fullmatch(r'(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}) UTC\+02:00', value)
        if match:
            timestamp, status = parse_time(match.group(1))
            return timestamp, 'valid_kyiv_wall_clock' if status == 'valid' else status
    return parse_time(value)
