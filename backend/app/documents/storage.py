"""Object storage for original case documents (MinIO via the minio client).

Keys are always cases/{case_id}/documents/{document_id}. Bucket and credentials
come from Settings (environment). Missing configuration raises
StorageNotConfigured, which endpoints report as NOT_CONFIGURED.
"""

import io
from typing import Protocol
from uuid import UUID

from app.config import Settings


class StorageNotConfigured(RuntimeError):
    pass


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...


def document_key(case_id: UUID, document_id: UUID) -> str:
    return f"cases/{case_id}/documents/{document_id}"


class MinioStore:
    def __init__(self, settings: Settings):
        from minio import Minio

        if not all((settings.minio_endpoint, settings.minio_access_key, settings.minio_secret_key,
                    settings.minio_bucket)):
            raise StorageNotConfigured("MinIO endpoint, credentials, and bucket are required")
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._create_bucket = settings.app_env != "production"
        self._bucket_ready = False

    def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        if not self.client.bucket_exists(self.bucket):
            if not self._create_bucket:
                raise StorageNotConfigured("Document bucket does not exist")
            self.client.make_bucket(self.bucket)
        self._bucket_ready = True

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._ensure_bucket()
        self.client.put_object(self.bucket, key, io.BytesIO(data), len(data), content_type=content_type)

    def get(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()


def get_store(settings: Settings) -> ObjectStore:
    return MinioStore(settings)
