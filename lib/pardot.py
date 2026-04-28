import time

import requests


class PardotClient:
    """Minimal REST client for the Pardot v5 API.

    Accepts the OAuth access_token_response dict so that auth concerns stay
    in auth.py and this class stays focused on HTTP mechanics.
    """

    def __init__(self, access_token_response: dict, pardot_base_url: str, business_unit_id: str):
        self._access_token = access_token_response['access_token']
        self._base_url = pardot_base_url.rstrip('/')
        self._business_unit_id = business_unit_id
        self.api_call_count = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self._access_token}',
            'Pardot-Business-Unit-Id': self._business_unit_id,
            'Content-Type': 'application/json',
        }

    def _make_url(self, path: str) -> str:
        return f'{self._base_url}/api/v5/objects/{path.lstrip("/")}'

    def _do_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Execute a single HTTP request and raise on non-2xx responses."""
        self.api_call_count += 1
        resp = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        if resp.status_code >= 400:
            body = (resp.text or '')[:500]
            raise RuntimeError(f'HTTP {resp.status_code} {resp.reason}: {body}')
        return resp

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Execute a request, retrying once on any failure (network or HTTP error)."""
        try:
            return self._do_request(method, url, **kwargs)
        except (requests.RequestException, RuntimeError):
            time.sleep(2)
            return self._do_request(method, url, **kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, path: str, params: dict = None) -> dict:
        """Single GET request. Returns parsed JSON."""
        url = self._make_url(path)
        kwargs = {'params': params} if params else {}
        return self._request('GET', url, **kwargs).json()

    def get_all(self, path: str, params: dict = None) -> list:
        """Paginated GET. Fetches all pages and returns a combined list.

        Uses limit=1000 by default. Follows nextPageUrl for subsequent pages
        as recommended by the v5 API docs (the URL already encodes the token
        and fields; no extra params should be sent with it).
        """
        params = dict(params or {})
        params.setdefault('limit', 1000)

        results = []
        url = self._make_url(path)
        current_params = params

        while url:
            kwargs = {'params': current_params} if current_params is not None else {}
            resp = self._request('GET', url, **kwargs)
            data = resp.json()
            results.extend(data.get('values', []))

            next_token = data.get('nextPageToken')
            next_url = data.get('nextPageUrl')

            if next_token and next_url:
                # nextPageUrl is a convenience URL with everything encoded;
                # send it as-is with no additional params per API docs.
                url = next_url
                current_params = None
            else:
                break

        return results

    def patch(self, path: str, data: dict) -> dict:
        """PATCH request. Returns parsed JSON, or empty dict for 204 No Content."""
        url = self._make_url(path)
        resp = self._request('PATCH', url, json=data)
        return resp.json() if resp.content else {}
