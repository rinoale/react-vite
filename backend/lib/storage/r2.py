import boto3
from botocore.exceptions import ClientError

from lib.storage.base import FileStorage


class R2FileStorage(FileStorage):
    """Store files in Cloudflare R2 (S3-compatible API)."""

    def __init__(self, account_id: str, access_key_id: str, secret_access_key: str,
                 bucket_name: str, prefix: str = ""):
        self._s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )
        self._bucket = bucket_name
        self._prefix = prefix.rstrip("/")

    def _key(self, key: str) -> str:
        if self._prefix:
            return f"{self._prefix}/{key}"
        return key

    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        full_key = self._key(key)
        self._s3.put_object(
            Bucket=self._bucket,
            Key=full_key,
            Body=data,
            ContentType=content_type,
        )
        return full_key

    def download(self, key: str) -> bytes:
        resp = self._s3.get_object(Bucket=self._bucket, Key=self._key(key))
        return resp["Body"].read()

    def delete(self, key: str) -> None:
        try:
            self._s3.delete_object(Bucket=self._bucket, Key=self._key(key))
        except ClientError:
            pass
