"""Resilient HTTP client for bdlaws.minlaw.gov.bd.

Handles session reuse, custom timeouts, retry backoff, and robust charset decoding
(specifically handling UTF-16, UTF-8, and header mismatches).
"""

import logging
import time
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

logger = logging.getLogger(__name__)


class BDLawsClient:
    """HTTP Client tailored for bdlaws.minlaw.gov.bd."""

    def __init__(
        self,
        base_url: str = config.BASE_URL,
        delay: float = config.REQUEST_DELAY,
        timeout: int = config.REQUEST_TIMEOUT,
        max_retries: int = config.MAX_RETRIES,
        backoff_factor: float = config.BACKOFF_FACTOR,
    ):
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(config.DEFAULT_HEADERS)

        # Configure urllib3 retry strategy for transport-level issues
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforces configured delay between sequential requests."""
        if self.delay > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def get_html(self, url: str, params: Optional[dict] = None) -> Optional[str]:
        """Fetches a URL and returns properly decoded HTML string.

        Args:
            url: Absolute or relative URL.
            params: Optional query parameters.

        Returns:
            Decoded HTML string, or None if request failed.
        """
        if not url.startswith("http"):
            url = f"{self.base_url}/{url.lstrip('/')}"

        self._rate_limit()

        try:
            logger.debug("GET %s (params=%s)", url, params)
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            if response.status_code != 200:
                logger.warning("HTTP status %s for URL: %s", response.status_code, url)
                return None

            return self.decode_response_content(response)

        except requests.RequestException as e:
            logger.error("Request failed for %s: %s", url, e)
            return None

    @staticmethod
    def decode_response_content(response: requests.Response) -> str:
        """Accurately decodes response content, handling server header quirks."""
        raw_bytes = response.content

        # List candidate encodings in priority order
        encodings = []
        if response.encoding:
            encodings.append(response.encoding.lower())
        if response.apparent_encoding:
            encodings.append(response.apparent_encoding.lower())
        
        # Standard fallbacks for bdlaws.minlaw.gov.bd
        for candidate in ["utf-16", "utf-8", "utf-16le", "utf-16be", "iso-8859-1"]:
            if candidate not in encodings:
                encodings.append(candidate)

        for enc in encodings:
            try:
                decoded = raw_bytes.decode(enc)
                # Verify that it doesn't look like null-byte padded text or replacement soup
                if "<html" in decoded.lower() or "<!doctype" in decoded.lower():
                    return decoded
            except (UnicodeDecodeError, LookupError):
                continue

        # Safe fallback with errors='replace' using utf-8
        return raw_bytes.decode("utf-8", errors="replace")

    def close(self) -> None:
        """Closes the underlying requests session."""
        self.session.close()
