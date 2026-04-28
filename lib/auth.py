import os

import requests

PARDOT_BASE_URLS = {
    'production': 'https://pi.pardot.com',
    'sandbox': 'https://pi.demo.pardot.com',
    'demo': 'https://pi.demo.pardot.com',
}


# Small helper to make OAuth POSTs robust and provide actionable errors without leaking secrets
def retrieve_oauth_token(url: str, data: dict, timeout: int = 30) -> dict:
    resp = requests.post(url, data=data, timeout=timeout)
    content_type = resp.headers.get('Content-Type', '')
    if resp.status_code >= 400:
        # Truncate body to avoid flooding logs; do not include secrets (we only log response)
        body_preview = (resp.text or '')[:500]
        raise RuntimeError(
            f"OAuth token request failed: {resp.status_code} {resp.reason}; "
            f"Content-Type: {content_type}; Body: {body_preview}"
        )
    try:
        return resp.json()
    except Exception:
        body_preview = (resp.text or '')[:500]
        raise RuntimeError(
            f"OAuth token response not JSON; Content-Type: {content_type}; Body: {body_preview}"
        )


def get_access_token() -> dict:
    sf_url = os.environ['SF_URL'].rstrip('/')
    return retrieve_oauth_token(
        sf_url + '/services/oauth2/token',
        data={
            'grant_type': 'client_credentials',
            'client_id': os.environ['CLIENT_ID'],
            'client_secret': os.environ['CLIENT_SECRET'],
        },
    )


def get_pardot_base_url() -> str:
    org_type = os.environ.get('PARDOT_ORG_TYPE', 'production').lower().strip()
    if org_type not in PARDOT_BASE_URLS:
        raise ValueError(
            f"Invalid PARDOT_ORG_TYPE '{org_type}'. Must be one of: {', '.join(PARDOT_BASE_URLS)}"
        )
    return PARDOT_BASE_URLS[org_type]
