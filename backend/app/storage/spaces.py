"""Object storage: DigitalOcean Spaces (S3-compatible, private ACL) with a local-filesystem fallback.

The local backend has the same interface so switching is only a matter of STORAGE_BACKEND.
Local presigned URLs are signed, short-lived tokens served by GET /api/v1/files/{token}.
"""

import time
from pathlib import Path
from typing import Protocol

import boto3
import jwt
from botocore.config import Config

from app.core.config import get_settings


class Storage(Protocol):
    def upload(self, key: str, data: bytes, content_type: str) -> None: ...
    def download(self, key: str) -> bytes: ...
    def presign(self, key: str, expires: int = 300) -> str: ...
    def delete(self, key: str) -> None: ...
    def head_bucket(self) -> None: ...


class SpacesStorage:
    def __init__(self) -> None:
        s = get_settings()
        self.bucket = s.spaces_bucket
        self.client = boto3.client(
            "s3",
            region_name=s.spaces_region,
            endpoint_url=s.spaces_endpoint,
            aws_access_key_id=s.spaces_key,
            aws_secret_access_key=s.spaces_secret,
            config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=30, retries={"max_attempts": 2}),
        )

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type, ACL="private")

    def download(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def presign(self, key: str, expires: int = 300) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def head_bucket(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)


class LocalStorage:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or get_settings().local_storage_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("invalid storage key")
        return path

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def download(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def presign(self, key: str, expires: int = 300) -> str:
        token = jwt.encode(
            {"key": key, "exp": int(time.time()) + expires, "typ": "file"},
            get_settings().jwt_secret,
            algorithm="HS256",
        )
        return f"/api/v1/files/{token}"

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def head_bucket(self) -> None:
        if not self.root.is_dir():
            raise FileNotFoundError(str(self.root))

    def resolve_token(self, token: str) -> str:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        if payload.get("typ") != "file":
            raise jwt.InvalidTokenError("wrong token type")
        return payload["key"]


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = SpacesStorage() if get_settings().storage_backend == "spaces" else LocalStorage()
    return _storage


# Module-level convenience functions matching the plan's interface.
def upload(key: str, data: bytes, content_type: str) -> None:
    get_storage().upload(key, data, content_type)


def download(key: str) -> bytes:
    return get_storage().download(key)


def presign(key: str, expires: int = 300) -> str:
    return get_storage().presign(key, expires)


def delete(key: str) -> None:
    get_storage().delete(key)
