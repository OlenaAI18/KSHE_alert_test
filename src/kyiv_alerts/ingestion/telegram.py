"""Linear traversal of Telegram HTML ZIP members; media is never read."""
from pathlib import Path, PurePosixPath
import re
from zipfile import ZipFile
from lxml import etree
from .timeutils import parse_telegram_time, valid_status

ID = re.compile(r'^message(-?\d+)$')


def has_class(element, name):
    return name in element.get('class', '').split()


def readable_text(element):
    """Preserve source text, entities and explicit HTML block/BR boundaries."""
    pieces = []
    def walk(node):
        if node.text:
            pieces.append(node.text)
        for child in node:
            if not isinstance(child.tag, str):
                if child.tail:
                    pieces.append(child.tail)
                continue
            tag = child.tag.lower()
            if tag == 'br':
                pieces.append('\n')
            else:
                if tag in {'p', 'div', 'blockquote', 'li'} and pieces and not pieces[-1].endswith('\n'):
                    pieces.append('\n')
                walk(child)
                if tag in {'p', 'div', 'blockquote', 'li'}:
                    pieces.append('\n')
            if child.tail:
                pieces.append(child.tail)
    walk(element)
    return ''.join(pieces).strip()


def safe_member(name):
    path = PurePosixPath(name.replace('\\', '/'))
    return not path.is_absolute() and '..' not in path.parts and not re.match(r'^[A-Za-z]:', name)


def member_order(name):
    """Natural page order: messages2.html precedes messages10.html."""
    name = name[:-5] if name.lower().endswith('.html') else name
    return tuple((1, int(part)) if part.isdigit() else (0, part)
                 for part in re.split(r'(\d+)', name))


def parse_telegram(path: Path):
    rows, duplicates, files, unsafe, errors = [], [], [], [], []
    seen = {}
    with ZipFile(path) as archive:
        members = sorted(archive.infolist(), key=lambda i: member_order(i.filename))
        html_count = sum(i.filename.lower().endswith('.html') for i in members)
        for member in members:
            if not member.filename.lower().endswith('.html'):
                continue
            if not safe_member(member.filename):
                unsafe.append(member.filename)
                continue
            # Read one HTML member at a time; no extraction and no asset access.
            parser = etree.HTMLParser(recover=True, no_network=True, encoding='utf-8')
            try:
                with archive.open(member) as stream:
                    document = etree.parse(stream, parser)
            except (etree.LxmlError, ValueError) as exc:
                errors.append({'source_file': member.filename, 'error': str(exc)})
                continue
            if parser.error_log:
                errors.append({'source_file': member.filename,
                               'html_recovery_errors': len(parser.error_log)})
            count = 0
            for element in document.iter('div'):
                if not has_class(element, 'message'):
                    continue
                count += 1
                source_id = element.get('id')
                match = ID.fullmatch(source_id or '')
                message_id = match.group(1) if match and not match.group(1).startswith('-') else None
                issues = []
                if message_id is None:
                    issues.append('export_service_identifier' if match and match.group(1).startswith('-') else 'missing_or_unrecognized_identifier')
                metadata = {}
                text_parts = []
                for child in element.iterdescendants():
                    if not isinstance(child.tag, str):
                        continue
                    classes = set(child.get('class', '').split())
                    if 'date' in classes and child.get('title') and 'date' not in metadata:
                        metadata['date'] = child.get('title')
                    if 'text' in classes and 'text' not in metadata:
                        metadata['text'] = readable_text(child)
                    if 'forwarded' in classes:
                        metadata['forwarded'] = child
                    if 'reply_to' in classes:
                        metadata['reply'] = child
                    if 'edited' in classes:
                        metadata['edited'] = child.get('title') or None
                time_original = metadata.get('date')
                timestamp, status = parse_telegram_time(time_original)
                if not valid_status(status):
                    issues.append(f'timestamp_{status}')
                is_service = has_class(element, 'service')
                text = metadata.get('text')
                if text is None and is_service:
                    # Service bodies can contain a date-only heading or a readable event.
                    for child in element.iterdescendants('div'):
                        if has_class(child, 'body'):
                            text_parts.append(readable_text(child))
                    text = '\n'.join(text_parts) or None
                forwarded = None
                if 'forwarded' in metadata:
                    for child in metadata['forwarded'].iter():
                        if has_class(child, 'from_name'):
                            forwarded = readable_text(child) or None
                            break
                reply = None
                if 'reply' in metadata:
                    for child in metadata['reply'].iter('a'):
                        reply_match = re.search(r'(?:#|^)(?:go_to_)?message(-?\d+)$', child.get('href', ''))
                        if reply_match:
                            reply = reply_match.group(1)
                            break
                row = {
                    'message_id': message_id, 'message_time_original': time_original,
                    'message_time': timestamp, 'text': text,
                    'message_type': 'service' if is_service else 'message',
                    'source_file': member.filename, 'source_message_index': count - 1,
                    'source_html_id': source_id,
                    'has_text': bool(text and text.strip()), 'is_service_message': is_service,
                    'forwarded_from': forwarded, 'reply_to_message_id': reply,
                    'edited_at': metadata.get('edited'),
                    'parse_status': ';'.join(issues) or 'valid',
                    'timestamp_status': status,
                }
                # Negative export heading IDs are not genuine Telegram IDs; preserve them
                # in source_html_id without inventing message IDs or deduplicating headings.
                # A repeated genuine ID is audited and retained once in deterministic file order.
                if message_id is not None and message_id in seen:
                    original = rows[seen[message_id]]
                    duplicates.append({'message_id': message_id, 'source_file': member.filename,
                                       'source_message_index': count - 1,
                                       'retained_source_file': original['source_file'],
                                       'conflicting_content': any(row[k] != original[k] for k in
                                           ['message_id', 'message_time_original', 'message_time', 'text', 'message_type',
                                            'has_text', 'is_service_message', 'forwarded_from', 'reply_to_message_id',
                                            'edited_at', 'parse_status', 'timestamp_status']),
                                       'duplicate_record': row})
                else:
                    if message_id is not None:
                        seen[message_id] = len(rows)
                    rows.append(row)
            if count:
                files.append({'source_file': member.filename, 'message_elements': count})
    return rows, {'html_members_discovered': html_count, 'message_html_files': files,
                  'duplicate_identifier_occurrences': duplicates,
                  'unsafe_html_members_skipped': unsafe, 'html_parse_errors': errors,
                  'message_elements': sum(f['message_elements'] for f in files)}
