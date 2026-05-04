import csv
import json
import sys
import time
from pathlib import Path

CSV_FILENAME = 'email_templates.csv'
CSV_FIELDNAMES = [
    'id', 'name', 'subject', 'campaign_name',
    'createdAt', 'updatedAt',
    'ready_to_update', 'update_status', 'html_file_path', 'text_file_path',
]

_READY_VALUES = {'yes', 'true', '1'}

BACKUP_FILENAME = 'template-metadata-backup.json'

# Full metadata backup fields requested for import safety.
BACKUP_FIELDS = [
    'id',
    'name',
    'isOneToOneEmail',
    'isDeleted',
    'isAutoResponderEmail',
    'isDripEmail',
    'isListEmail',
    'replyToOptions.type',
    'replyToOptions.address',
    'replyToOptions.userId',
    'replyToOptions.prospectCustomFieldId',
    'replyToOptions.accountCustomFieldId',
    'senderOptions.type',
    'senderOptions.address',
    'senderOptions.name',
    'senderOptions.userId',
    'senderOptions.prospectCustomFieldId',
    'senderOptions.accountCustomFieldId',
    'subject',
    'type',
    'createdAt',
    'updatedAt',
    'createdById',
    'updatedById',
    'trackerDomainId',
    'campaignId',
    'folderId',
    'tagReplacementLanguage',
]

# Writable template fields we can safely preserve during PATCH.
PATCH_PASSTHROUGH_FIELDS = [
    'name',
    'isOneToOneEmail',
    'isAutoResponderEmail',
    'isDripEmail',
    'isListEmail',
    'replyToOptions',
    'senderOptions',
    'subject',
    'type',
    'trackerDomainId',
    'campaignId',
    'folderId',
]


def _read_csv(csv_path) -> list:
    with open(csv_path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _write_csv(rows: list, csv_path) -> None:
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _build_patch_payload(metadata: dict, html_content: str, txt_content: str) -> dict:
    payload = {
        'htmlMessage': html_content,
        'textMessage': txt_content,
    }
    for key in PATCH_PASSTHROUGH_FIELDS:
        if key in metadata and metadata[key] is not None:
            payload[key] = metadata[key]
    return payload


def run_import(client, working_dir: str = None) -> None:
    start_time = time.time()

    base = Path(working_dir) if working_dir else Path('.')
    csv_path = base / CSV_FILENAME

    if not csv_path.exists():
        print(f"Error: '{csv_path}' not found. Run extract first, then pass --dir to import.")
        sys.exit(1)

    rows = _read_csv(csv_path)
    ready_rows = [
        r for r in rows
        if r.get('ready_to_update', '').strip().lower() in _READY_VALUES
        and not r.get('update_status', '').strip()
    ]

    if not ready_rows:
        print('No rows marked "Ready to Update". Set the ready_to_update column to Yes and re-run.')
        return

    # ------------------------------------------------------------------ #
    # Pre-flight: verify every file reference exists before touching the  #
    # API. Abort immediately if anything is missing.                      #
    # ------------------------------------------------------------------ #
    for row in ready_rows:
        html_path = row.get('html_file_path', '').strip()
        txt_path = row.get('text_file_path', '').strip()
        name = row.get('name', row.get('id', '?'))

        if not html_path or not Path(html_path).is_file():
            print(f"Error: HTML file not found for '{name}': {html_path!r}")
            sys.exit(1)
        if not txt_path or not Path(txt_path).is_file():
            print(f"Error: Text file not found for '{name}': {txt_path!r}")
            sys.exit(1)

    print(f'Found {len(ready_rows)} template(s) ready to update.\n')

    updated = 0
    abort = False

    try:
        for row in rows:
            if row.get('ready_to_update', '').strip().lower() not in _READY_VALUES:
                continue
            if row.get('update_status', '').strip():
                continue

            tmpl_id = row['id']
            tmpl_name = row.get('name', tmpl_id)
            html_path = row['html_file_path'].strip()
            txt_path = row['text_file_path'].strip()
            backup_dir = Path(html_path).parent

            print(f'  Updating: {tmpl_name}')

            # ---------------------------------------------------------- #
            # Step 1: Download a fresh backup before making any changes.  #
            # ---------------------------------------------------------- #
            try:
                current = client.get(
                    f'email-templates/{tmpl_id}',
                    {'fields': ','.join(BACKUP_FIELDS + ['htmlMessage', 'textMessage'])},
                )
                (backup_dir / 'content-backup.html').write_text(
                    current.get('htmlMessage') or '', encoding='utf-8'
                )
                (backup_dir / 'content-backup.txt').write_text(
                    current.get('textMessage') or '', encoding='utf-8'
                )
                (backup_dir / BACKUP_FILENAME).write_text(
                    json.dumps(current, indent=2, sort_keys=True),
                    encoding='utf-8',
                )
            except Exception as exc:
                row['update_status'] = f'Error: backup failed: {exc}'
                print(f'    Error (backup): {exc}')
                abort = True
                break

            # ---------------------------------------------------------- #
            # Step 2: Read local files and PATCH the template.            #
            # ---------------------------------------------------------- #
            try:
                html_content = Path(html_path).read_text(encoding='utf-8')
                txt_content = Path(txt_path).read_text(encoding='utf-8')
                payload = _build_patch_payload(current, html_content, txt_content)
                csv_subject = row.get('subject', '').strip()
                if csv_subject:
                    payload['subject'] = csv_subject
                client.patch(
                    f'email-templates/{tmpl_id}',
                    payload,
                )
                row['update_status'] = 'Success'
                updated += 1
                print(f'    Done.')
            except Exception as exc:
                row['update_status'] = f'Error: {exc}'
                print(f'    Error (update): {exc}')
                abort = True
                break

    finally:
        # Always write the CSV and print stats — even on abort.
        _write_csv(rows, csv_path)

        elapsed = time.time() - start_time
        status = 'aborted' if abort else 'complete'
        print(f'\nImport {status}.')
        print(f'  Templates updated : {updated}')
        print(f'  API calls made    : {client.api_call_count}')
        print(f'  Time elapsed      : {elapsed:.1f}s')

    if abort:
        sys.exit(1)
