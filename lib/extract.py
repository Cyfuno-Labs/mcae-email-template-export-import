import csv
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

CSV_FILENAME = 'email_templates.csv'
CSV_FIELDNAMES = [
    'id', 'name', 'subject', 'campaign_name',
    'createdAt', 'updatedAt',
    'ready_to_update', 'update_status', 'html_file_path', 'text_file_path',
]


def _sanitize_dirname(name: str) -> str:
    """Replace characters that are invalid in directory names (Windows-safe)."""
    sanitized = re.sub(r'[<>:"/\\|?*\r\n\t\x00-\x1f]', '_', name).strip().strip('.')
    return sanitized[:100] or 'unnamed'


def run_extract(
    client,
    filter_name=None,
    filter_campaign=None,
    filter_tags=None,
    filter_created_at_after=None,
    prompt_created_at_after=False,
):
    start_time = time.time()

    # ------------------------------------------------------------------ #
    # Optional: prompt for createdAtAfter date filter                     #
    # ------------------------------------------------------------------ #
    if prompt_created_at_after:
        default_dt = (
            datetime.now().astimezone() - timedelta(days=30)
        ).isoformat(timespec='seconds')
        raw = input(f'Created after date [{default_dt}]: ').strip()
        filter_created_at_after = raw if raw else default_dt

    # ------------------------------------------------------------------ #
    # Step 1: Query all email templates (htmlMessage/textMessage are not  #
    # queryable, so we only fetch relational fields here).                #
    # ------------------------------------------------------------------ #
    print('Querying email templates...')
    query_params = {
        'fields': 'id,name,subject,createdAt,updatedAt,campaignId,campaign.name',
    }
    if filter_created_at_after:
        query_params['createdAtAfter'] = filter_created_at_after

    all_templates = client.get_all('email-templates', query_params)

    # ------------------------------------------------------------------ #
    # Step 2: Apply client-side filters                                   #
    # ------------------------------------------------------------------ #
    templates = list(all_templates)

    if filter_name:
        templates = [
            t for t in templates
            if filter_name.lower() in (t.get('name') or '').lower()
        ]

    if filter_campaign:
        templates = [
            t for t in templates
            if filter_campaign.lower() in ((t.get('campaign') or {}).get('name') or '').lower()
        ]

    # Tags require API lookups: resolve names → IDs → tagged-object IDs, then intersect.
    found_tag_count = 0
    if filter_tags:
        tag_names_requested = [n.strip() for n in filter_tags.split(',') if n.strip()]
        id_sets = []

        for tag_name in tag_names_requested:
            matching_tags = client.get_all('tags', {'fields': 'id,name', 'name': tag_name})
            if not matching_tags:
                print(f"Warning: tag '{tag_name}' not found — result set will be empty.")
                id_sets.append(set())
                continue

            found_tag_count += len(matching_tags)
            tag_template_ids = set()
            for tag in matching_tags:
                tagged = client.get_all('tagged-objects', {
                    'fields': 'objectId',
                    'tagId': tag['id'],
                    'objectType': 'email-template',
                })
                tag_template_ids.update(obj['objectId'] for obj in tagged)
            id_sets.append(tag_template_ids)

        if id_sets:
            valid_ids = id_sets[0]
            for s in id_sets[1:]:
                valid_ids = valid_ids & s
            templates = [t for t in templates if t['id'] in valid_ids]

    # ------------------------------------------------------------------ #
    # Step 3: Confirm with user                                           #
    # ------------------------------------------------------------------ #
    if not templates:
        print('No email templates found matching the specified filters.')
        return

    active_filter_lines = []
    if filter_name:
        active_filter_lines.append(f'  name contains   : {filter_name}')
    if filter_campaign:
        active_filter_lines.append(f'  campaign        : {filter_campaign}')
    if filter_tags:
        active_filter_lines.append(f'  tags            : {filter_tags}')
    if filter_created_at_after:
        active_filter_lines.append(f'  created after   : {filter_created_at_after}')

    if active_filter_lines:
        print('Active filters:')
        for line in active_filter_lines:
            print(line)

    prompt = f'We found {len(templates)} email template(s). Proceed? (y/N): '

    answer = input(prompt).strip().lower()
    if answer not in ('y', 'yes'):
        print('Aborted.')
        return

    # ------------------------------------------------------------------ #
    # Step 3b: Ask where to save the working directory.                  #
    # ------------------------------------------------------------------ #
    default_dir = datetime.now().strftime('extract_%Y%m%d_%H%M%S')
    raw = input(f'Save files to directory [{default_dir}]: ').strip()
    working_dir = Path(raw if raw else default_dir)

    if working_dir.exists() and any(working_dir.iterdir()):
        confirm = input(
            f"Directory '{working_dir}' already exists and is not empty. Continue? (y/N): "
        ).strip().lower()
        if confirm not in ('y', 'yes'):
            print('Aborted.')
            return

    working_dir.mkdir(parents=True, exist_ok=True)
    print(f"Saving to '{working_dir}'\n")

    # ------------------------------------------------------------------ #
    # Step 4: For each template, READ to get htmlMessage and textMessage, #
    # write files, and build CSV rows.                                    #
    # NOTE: These fields are not queryable so a separate GET is required. #
    # ------------------------------------------------------------------ #
    rows = []
    downloaded = 0
    total = len(templates)

    for tmpl in templates:
        tmpl_id = tmpl['id']
        campaign_name = ((tmpl.get('campaign') or {}).get('name') or 'No Campaign')
        email_name = (tmpl.get('name') or f'template_{tmpl_id}')

        detail = client.get(
            f'email-templates/{tmpl_id}',
            {'fields': 'id,htmlMessage,textMessage'},
        )
        html_message = detail.get('htmlMessage') or ''
        text_message = detail.get('textMessage') or ''

        template_dir = working_dir / _sanitize_dirname(campaign_name) / _sanitize_dirname(email_name)
        template_dir.mkdir(parents=True, exist_ok=True)

        (template_dir / 'content-original.html').write_text(html_message, encoding='utf-8')
        (template_dir / 'content-updated.html').write_text(html_message, encoding='utf-8')
        (template_dir / 'content-original.txt').write_text(text_message, encoding='utf-8')
        (template_dir / 'content-updated.txt').write_text(text_message, encoding='utf-8')

        rows.append({
            'id': tmpl_id,
            'name': email_name,
            'subject': (tmpl.get('subject') or ''),
            'campaign_name': campaign_name,
            'createdAt': (tmpl.get('createdAt') or ''),
            'updatedAt': (tmpl.get('updatedAt') or ''),
            'ready_to_update': 'No',
            'html_file_path': str(template_dir / 'content-updated.html'),
            'text_file_path': str(template_dir / 'content-updated.txt'),
            'update_status': '',
        })

        downloaded += 1
        print(f'  [{downloaded}/{total}] {email_name}')

    # ------------------------------------------------------------------ #
    # Step 5: Write CSV into the working directory.                       #
    # ------------------------------------------------------------------ #
    csv_path = working_dir / CSV_FILENAME
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    elapsed = time.time() - start_time
    print(f'\nExtract complete.')
    print(f'  Templates downloaded : {downloaded}')
    print(f'  API calls made       : {client.api_call_count}')
    print(f'  Time elapsed         : {elapsed:.1f}s')
    print(f'  Saved to             : {working_dir}')
    print(f'  Spreadsheet          : {csv_path}')
