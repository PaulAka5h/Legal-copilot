"""Gemini embeddings (EMBEDDING_PROVIDER=gemini): gemini-embedding-001 by default.

Recipe (embedding_version GEMINI_EMBEDDING_VERSION; change the number if any of it
changes, so stored chunk vectors and query vectors can never be mixed silently):
- input is NFC text, no e5 "query: "/"passage: " prefix;
- task_type RETRIEVAL_DOCUMENT for legal chunks, RETRIEVAL_QUERY for searches;
- output_dimensionality 1024 (Matryoshka truncation, fits the vector(1024) column);
- every vector is L2-normalized after truncation (truncated vectors are not unit
  length, and search uses cosine distance on unit vectors).

Requests go to batchEmbedContents, at most GEMINI_BATCH_MAX texts each, and are
retried with exponential backoff on 429 and 5xx (honouring the server's retry
delay). The free tier counts every text in a batch as one request (100 per minute
per model), and rejected attempts count too, so blind retries of large batches can
keep the window full forever. Bulk embedding therefore paces itself
(texts_per_minute) to stay under the quota instead of relying on 429s. The text leaves the server: approved for SYNTHETIC SAMPLE DATA ONLY and
refused when APP_ENV=production (DOCS/providers.md). The key and the text are
never logged or put in error messages.
"""

import math
import re
import time
from collections import deque
from collections.abc import Callable, Sequence
from typing import Any

import httpx

from app.rag.search.errors import EmbeddingUnavailable
from app.rag.text import nfc

GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
GEMINI_EMBEDDING_VERSION = 1
GEMINI_DIM = 1024
GEMINI_BATCH_MAX = 100  # API limit per batchEmbedContents call
RETRY_STATUSES = {429, 500, 502, 503, 504}
TASK_QUERY = "RETRIEVAL_QUERY"
TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
_RETRY_DELAY = re.compile(r"^(\d+(?:\.\d+)?)s$")


class GeminiEmbeddingError(EmbeddingUnavailable):
    """The Gemini embedding call failed after retries, or answered something unusable (503)."""


def l2_normalize(vector: Sequence[float]) -> list[float]:
    values = [float(v) for v in vector]
    norm = math.sqrt(sum(v * v for v in values))
    if not norm or not math.isfinite(norm):
        raise GeminiEmbeddingError("Gemini returned a zero or non-finite vector")
    return [v / norm for v in values]


def _server_retry_delay(response: httpx.Response) -> float | None:
    """Seconds the server asked us to wait (Retry-After header or google.rpc.RetryInfo)."""
    header = response.headers.get("retry-after")
    if header and header.replace(".", "", 1).isdigit():
        return float(header)
    try:
        details = response.json().get("error", {}).get("details", [])
    except ValueError:
        return None
    for detail in details if isinstance(details, list) else []:
        match = _RETRY_DELAY.match(str(detail.get("retryDelay", ""))) if isinstance(detail, dict) else None
        if match:
            return float(match.group(1))
    return None


class GeminiEmbeddingClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout: float = 30.0,
        attempts: int = 4,
        backoff: float = 1.0,
        max_wait: float = 65.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        texts_per_minute: int | None = None,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
            raise ValueError("GEMINI_EMBEDDING_MODEL must be a bare model name, e.g. gemini-embedding-001")
        self.model = model
        self._url = GEMINI_EMBED_URL.format(model=model)
        self._headers = {"x-goog-api-key": api_key}
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._attempts, self._backoff, self._max_wait, self._sleep = attempts, backoff, max_wait, sleep
        self._clock, self._per_minute = clock, texts_per_minute
        self._sent: deque[tuple[float, int]] = deque()  # (time, texts) in the last minute
        self._batch_max = min(GEMINI_BATCH_MAX, texts_per_minute or GEMINI_BATCH_MAX)

    def embed(self, texts: Sequence[str], task_type: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_max):
            vectors += self._embed_batch(texts[start:start + self._batch_max], task_type)
        return vectors

    def _pace(self, count: int) -> None:
        """Block until sending `count` more texts keeps the last 60 s within texts_per_minute."""
        if not self._per_minute:
            return
        while True:
            now = self._clock()
            while self._sent and now - self._sent[0][0] >= 60:
                self._sent.popleft()
            if sum(n for _, n in self._sent) + count <= self._per_minute:
                self._sent.append((now, count))
                return
            self._sleep(60 - (now - self._sent[0][0]) + 0.5)

    def _embed_batch(self, texts: Sequence[str], task_type: str) -> list[list[float]]:
        body = {"requests": [
            {"model": f"models/{self.model}", "content": {"parts": [{"text": nfc(t)}]},
             "taskType": task_type, "outputDimensionality": GEMINI_DIM}
            for t in texts
        ]}
        payload = self._post(body)
        embeddings = payload.get("embeddings") if isinstance(payload, dict) else None
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise GeminiEmbeddingError("Gemini returned an unexpected number of embeddings")
        out = []
        for item in embeddings:
            values = item.get("values") if isinstance(item, dict) else None
            if not isinstance(values, list) or len(values) != GEMINI_DIM:
                raise GeminiEmbeddingError(f"Gemini returned a vector that is not {GEMINI_DIM}-dimensional")
            try:
                out.append(l2_normalize(values))
            except (TypeError, ValueError) as error:
                raise GeminiEmbeddingError("Gemini returned non-numeric values") from error
        return out

    def _post(self, body: dict[str, Any]) -> Any:
        for attempt in range(1, self._attempts + 1):
            wait = self._backoff * 2 ** (attempt - 1)
            self._pace(len(body["requests"]))  # every attempt counts against the quota
            try:
                response = self._client.post(self._url, json=body, headers=self._headers)
            except httpx.HTTPError as error:
                if attempt == self._attempts:
                    raise GeminiEmbeddingError(f"Gemini unreachable: {type(error).__name__}") from error
            else:
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError as error:
                        raise GeminiEmbeddingError("Gemini returned invalid JSON") from error
                if response.status_code not in RETRY_STATUSES or attempt == self._attempts:
                    raise GeminiEmbeddingError(f"Gemini answered HTTP {response.status_code}")
                wait = max(wait, _server_retry_delay(response) or 0)
            self._sleep(min(wait, self._max_wait))
        raise GeminiEmbeddingError("Gemini embedding failed")  # unreachable


class GeminiQueryEmbedder:
    """Search side: one RETRIEVAL_QUERY vector. Few, short retries (a user is waiting)."""

    embedding_version = GEMINI_EMBEDDING_VERSION

    def __init__(self, client: GeminiEmbeddingClient) -> None:
        self.client = client
        self.model_name = client.model

    def embed_query(self, query: str) -> list[float]:
        return self.client.embed([query], TASK_QUERY)[0]


class GeminiDocumentEmbedder:
    """Knowledge-base side (python -m app.rag.embed): RETRIEVAL_DOCUMENT vectors."""

    device = "gemini-api"
    embedding_version = GEMINI_EMBEDDING_VERSION

    def __init__(self, client: GeminiEmbeddingClient) -> None:
        self.client = client
        self.model_name = client.model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.client.embed(texts, TASK_DOCUMENT)
