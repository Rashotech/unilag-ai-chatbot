import os
import uuid
from typing import Optional, Tuple
from firebase_admin import storage
from google.cloud.storage import Blob
from django.conf import settings
import logging
import mimetypes

logger = logging.getLogger(__name__)


class FirebaseStorageService:
    """Service for handling Firebase Cloud Storage operations"""

    def __init__(self):
        self.bucket = storage.bucket()
        self.base_path = 'documents/'

    def upload_file(self, file_obj, filename: str = None, folder: str = None) -> Tuple[bool, str, dict]:
        """
        Upload file to Firebase Storage

        Args:
            file_obj: Django file object
            filename: Optional custom filename
            folder: Optional folder path

        Returns:
            Tuple of (success, file_path, metadata)
        """
        try:
            # Generate unique filename if not provided
            if not filename:
                file_extension = os.path.splitext(file_obj.name)[1]
                filename = f"{uuid.uuid4()}{file_extension}"

            # Construct full path
            if folder:
                file_path = f"{self.base_path}{folder}/{filename}"
            else:
                file_path = f"{self.base_path}{filename}"

            # Get content type
            content_type = file_obj.content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'

            # Create blob and upload
            blob = self.bucket.blob(file_path)
            blob.upload_from_file(
                file_obj,
                content_type=content_type
            )

            # Make blob publicly readable (optional)
            # blob.make_public()

            # Get download URL (requires authentication)
            download_url = self._get_download_url(blob)

            metadata = {
                'name': filename,
                'size': file_obj.size,
                'content_type': content_type,
                'path': file_path,
                'url': download_url,
                'bucket': self.bucket.name,
            }

            logger.info(f"Successfully uploaded file to Firebase: {file_path}")
            return True, file_path, metadata

        except Exception as e:
            logger.error(f"Failed to upload file to Firebase: {e}")
            return False, str(e), {}

    def download_file(self, file_path: str) -> Optional[bytes]:
        """
        Download file from Firebase Storage

        Args:
            file_path: Path to file in storage

        Returns:
            File content as bytes or None if failed
        """
        try:
            blob = self.bucket.blob(file_path)
            if not blob.exists():
                logger.error(f"File not found in Firebase: {file_path}")
                return None

            content = blob.download_as_bytes()
            logger.info(f"Successfully downloaded file from Firebase: {file_path}")
            return content

        except Exception as e:
            logger.error(f"Failed to download file from Firebase: {e}")
            return None

    def delete_file(self, file_path: str) -> bool:
        """
        Delete file from Firebase Storage

        Args:
            file_path: Path to file in storage

        Returns:
            True if successful, False otherwise
        """
        try:
            blob = self.bucket.blob(file_path)
            if blob.exists():
                blob.delete()
                logger.info(f"Successfully deleted file from Firebase: {file_path}")
                return True
            else:
                logger.warning(f"File not found for deletion: {file_path}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete file from Firebase: {e}")
            return False

    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists in Firebase Storage

        Args:
            file_path: Path to file in storage

        Returns:
            True if file exists, False otherwise
        """
        try:
            blob = self.bucket.blob(file_path)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error checking file existence: {e}")
            return False

    def get_file_metadata(self, file_path: str) -> dict:
        """
        Get file metadata from Firebase Storage

        Args:
            file_path: Path to file in storage

        Returns:
            Dictionary with file metadata
        """
        try:
            blob = self.bucket.blob(file_path)
            if not blob.exists():
                return {}

            blob.reload()  # Refresh metadata

            return {
                'name': blob.name,
                'size': blob.size,
                'content_type': blob.content_type,
                'created': blob.time_created.isoformat() if blob.time_created else None,
                'updated': blob.updated.isoformat() if blob.updated else None,
                'etag': blob.etag,
                'generation': blob.generation,
                'url': self._get_download_url(blob),
            }

        except Exception as e:
            logger.error(f"Failed to get file metadata: {e}")
            return {}

    def list_files(self, prefix: str = None, limit: int = 100) -> list:
        """
        List files in Firebase Storage

        Args:
            prefix: Optional prefix to filter files
            limit: Maximum number of files to return

        Returns:
            List of file metadata dictionaries
        """
        try:
            blobs = self.bucket.list_blobs(
                prefix=prefix or self.base_path,
                max_results=limit
            )

            files = []
            for blob in blobs:
                files.append({
                    'name': blob.name,
                    'size': blob.size,
                    'content_type': blob.content_type,
                    'created': blob.time_created.isoformat() if blob.time_created else None,
                    'updated': blob.updated.isoformat() if blob.updated else None,
                })

            return files

        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []

    def _get_download_url(self, blob: Blob) -> str:
        """
        Get download URL for a blob (requires authentication)

        Args:
            blob: Storage blob object

        Returns:
            Download URL string
        """
        try:
            # For public access (if blob is public)
            return blob.public_url
        except:
            # For authenticated access, you might want to generate signed URLs
            # This requires additional setup for token-based access
            return f"gs://{self.bucket.name}/{blob.name}"

    def generate_signed_url(self, file_path: str, expiration_minutes: int = 60) -> Optional[str]:
        """
        Generate signed URL for temporary access to private files

        Args:
            file_path: Path to file in storage
            expiration_minutes: URL expiration time in minutes

        Returns:
            Signed URL string or None if failed
        """
        try:
            from datetime import datetime, timedelta

            blob = self.bucket.blob(file_path)
            if not blob.exists():
                return None

            expiration = datetime.utcnow() + timedelta(minutes=expiration_minutes)

            url = blob.generate_signed_url(
                version="v4",
                expiration=expiration,
                method="GET",
            )

            return url

        except Exception as e:
            logger.error(f"Failed to generate signed URL: {e}")
            return None

    def get_storage_usage(self) -> dict:
        """
        Get storage usage statistics

        Returns:
            Dictionary with usage statistics
        """
        try:
            blobs = self.bucket.list_blobs(prefix=self.base_path)

            total_size = 0
            file_count = 0
            file_types = {}

            for blob in blobs:
                total_size += blob.size or 0
                file_count += 1

                content_type = blob.content_type or 'unknown'
                file_types[content_type] = file_types.get(content_type, 0) + 1

            return {
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'file_count': file_count,
                'file_types': file_types,
            }

        except Exception as e:
            logger.error(f"Failed to get storage usage: {e}")
            return {}