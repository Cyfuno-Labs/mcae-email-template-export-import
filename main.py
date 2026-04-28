"""
MCAE / Pardot Mass Email Template Updater
==========================================
Usage:
    python main.py test-auth
    python main.py extract [--name "..."] [--campaign "..."] [--tags "tag1,tag2"]
    python main.py import [--dir PATH]

On first run (no .env present), the script copies .env-sample to .env,
prompts for each value, saves the file, then exits. Run again to proceed.
"""

import os
import shutil
import sys
from pathlib import Path

# Env keys and the human-readable prompts shown on first run.
_ENV_KEYS = [
    ('SF_URL',                  'Salesforce MyDomain URL  (e.g. https://yourorg.my.salesforce.com)'),
    ('CLIENT_ID',               'Salesforce External Client App (Consumer) Key'),
    ('CLIENT_SECRET',           'Salesforce External Client App (Consumer) Secret'),
    ('PARDOT_BUSINESS_UNIT_ID', 'Pardot Business Unit ID  (18-char string starting with 0Uv)'),
    ('PARDOT_ORG_TYPE',         'Pardot Org Type  [production / sandbox / demo]'),
]


def _get_required_env_value(key: str) -> str:
    value = os.environ.get(key, '').strip()
    if not value:
        raise ValueError(f'{key} is not set in .env')
    return value


def _build_pardot_client():
    from lib.auth import get_access_token, get_pardot_base_url
    from lib.pardot import PardotClient

    _get_required_env_value('SF_URL')
    _get_required_env_value('CLIENT_ID')
    _get_required_env_value('CLIENT_SECRET')
    business_unit_id = _get_required_env_value('PARDOT_BUSINESS_UNIT_ID')

    access_token_response = get_access_token()
    pardot_base_url = get_pardot_base_url()

    client = PardotClient(access_token_response, pardot_base_url, business_unit_id)
    return client, pardot_base_url, business_unit_id


def _run_test_auth() -> None:
    print('Checking configuration and authentication...')

    try:
        client, pardot_base_url, business_unit_id = _build_pardot_client()
        response = client.get('email-templates', {'fields': 'id,name', 'limit': 1})
    except ValueError as exc:
        print(f'Configuration error: {exc}')
        sys.exit(1)
    except RuntimeError as exc:
        print(f'Authentication/API error: {exc}')
        sys.exit(1)

    sample_count = len(response.get('values', []))
    print('Success.')
    print('  .env configuration   : OK')
    print('  Salesforce OAuth     : OK')
    print('  Pardot API access    : OK')
    print(f'  Pardot base URL      : {pardot_base_url}')
    print(f'  Business Unit ID     : {business_unit_id}')
    print(f'  Sample records read  : {sample_count}')
    print(f'  API calls made       : {client.api_call_count}')


def _first_run_setup() -> None:
    """Copy .env-sample to .env, prompt for each value, then exit."""
    env_sample = Path('.env-sample')
    env_file = Path('.env')

    if not env_sample.exists():
        print('Error: .env-sample not found. Please ensure it is present in the working directory.')
        sys.exit(1)

    shutil.copy(env_sample, env_file)
    print('No .env file found. Creating one now — please provide the following values:\n')

    lines = env_file.read_text(encoding='utf-8').splitlines()

    for key, description in _ENV_KEYS:
        value = input(f'{description}\n  {key}: ').strip()
        for i, line in enumerate(lines):
            if line.startswith(f'{key}='):
                lines[i] = f'{key}={value}'
                break

    env_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\nConfiguration saved to .env')
    print('Run the script again to proceed.')
    sys.exit(0)


def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        description='MCAE / Pardot Mass Email Template Updater',
        epilog=(
            'Examples:\n'
            '  python main.py test-auth\n'
            '  python main.py extract --tags "invitations"\n'
            '  python main.py extract --campaign "Annual Customer Conference"\n'
            '  python main.py import --dir extract_20260413_202850'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='command', required=True, metavar='command')

    subparsers.add_parser(
        'test-auth',
        help='Verify .env settings, Salesforce OAuth, and Pardot API access.',
        description='Check required configuration, Salesforce OAuth, and MCAE API access.',
    )

    extract_parser = subparsers.add_parser(
        'extract',
        help='Download email templates from MCAE into local files and a CSV.',
        description='Download matching email templates into a working folder and CSV.',
        epilog=(
            'Examples:\n'
            '  python main.py extract\n'
            '  python main.py extract --name "Webinar"\n'
            '  python main.py extract --campaign "Annual Customer Conference"\n'
            '  python main.py extract --tags "invitations,webinar"'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    extract_parser.add_argument(
        '--name',
        metavar='TEXT',
        help='Filter templates whose name contains TEXT (case-insensitive).',
    )
    extract_parser.add_argument(
        '--campaign',
        metavar='TEXT',
        help='Filter templates whose campaign name contains TEXT (case-insensitive).',
    )
    extract_parser.add_argument(
        '--tags',
        metavar='TAG1,TAG2',
        help='Filter templates tagged with ALL of the given tags (comma-separated, exact match).',
    )

    import_parser = subparsers.add_parser(
        'import',
        help='Upload updated template files back to MCAE for rows marked Ready to Update.',
        description='Upload edited HTML and text files for rows marked ready_to_update=Yes.',
        epilog='Example:\n  python main.py import --dir extract_20260413_202850',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    import_parser.add_argument(
        '--dir',
        metavar='PATH',
        help='Path to the working directory created by extract (contains email_templates.csv).',
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # ------------------------------------------------------------------ #
    # First-run check                                                     #
    # ------------------------------------------------------------------ #
    if not Path('.env').exists():
        _first_run_setup()

    # Load environment variables from .env
    from dotenv import load_dotenv
    load_dotenv()

    # ------------------------------------------------------------------ #
    # Dispatch                                                            #
    # ------------------------------------------------------------------ #
    if args.command == 'test-auth':
        _run_test_auth()
    elif args.command == 'extract':
        try:
            client, _, _ = _build_pardot_client()
        except ValueError as exc:
            print(f'Configuration error: {exc}')
            sys.exit(1)
        except RuntimeError as exc:
            print(f'Authentication/API error: {exc}')
            sys.exit(1)

        from lib.extract import run_extract
        run_extract(
            client,
            filter_name=args.name,
            filter_campaign=args.campaign,
            filter_tags=args.tags,
        )
    elif args.command == 'import':
        try:
            client, _, _ = _build_pardot_client()
        except ValueError as exc:
            print(f'Configuration error: {exc}')
            sys.exit(1)
        except RuntimeError as exc:
            print(f'Authentication/API error: {exc}')
            sys.exit(1)

        from lib.importer import run_import
        run_import(client, working_dir=args.dir)


if __name__ == '__main__':
    main()
