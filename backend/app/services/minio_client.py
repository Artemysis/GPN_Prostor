import io
from datetime import timedelta
from functools import lru_cache

from loguru import logger
from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

settings = get_settings()


class MinioService:
    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.buckets = [
            settings.minio_bucket_templates,
            settings.minio_bucket_exports,
            settings.minio_bucket_attachments,
            settings.minio_bucket_ingest,
        ]

    def ensure_buckets(self) -> None:
        for bucket in self.buckets:
            try:
                if not self.client.bucket_exists(bucket):
                    self.client.make_bucket(bucket)
            except S3Error as exc:
                logger.warning(f"MinIO недоступен, пропускаю создание бакета {bucket}: {exc}")

    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(bucket, key, io.BytesIO(data), length=len(data), content_type=content_type)

    def download_bytes(self, bucket: str, key: str) -> bytes:
        response = self.client.get_object(bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def presigned_url(self, bucket: str, key: str, expires_minutes: int = 15) -> str:
        return self.client.presigned_get_object(bucket, key, expires=timedelta(minutes=expires_minutes))

    def delete(self, bucket: str, key: str) -> None:
        self.client.remove_object(bucket, key)

    def object_exists(self, bucket: str, key: str) -> bool:
        try:
            self.client.stat_object(bucket, key)
            return True
        except S3Error:
            return False


@lru_cache
def get_minio_service() -> MinioService:
    return MinioService()
