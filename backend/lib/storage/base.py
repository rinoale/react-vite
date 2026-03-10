from abc import ABC, abstractmethod


class FileStorage(ABC):
    """Abstract base for file storage backends (Strategy pattern).

    Implementations: LocalFileStorage, GCSFileStorage, S3FileStorage.
    """

    @abstractmethod
    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload data and return the storage path/URL."""

    @abstractmethod
    def download(self, key: str) -> bytes:
        """Download and return file contents."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a file. No error if it doesn't exist."""
