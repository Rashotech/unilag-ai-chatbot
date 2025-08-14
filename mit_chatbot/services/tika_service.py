import requests
import logging
from typing import Dict, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


class TikaExtractionService:
    def __init__(self):
        self.tika_server_url = settings.TIKA_SERVER_URL
        self.timeout = getattr(settings, 'TIKA_TIMEOUT', 300)  # 2 minutes default

    def extract_content(self, file_content: bytes, filename: str = None) -> Tuple[bool, Dict]:
        """
        Extract content using direct API calls to Tika server

        Args:
            file_content: Document content as bytes
            filename: Original filename (optional, used for content type detection)

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Prepare headers
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/octet-stream'
            }

            # Add filename hint if provided
            if filename:
                headers['Content-Disposition'] = f'attachment; filename="{filename}"'

            # Make API call to Tika server
            response = requests.put(
                f"{self.tika_server_url}/tika",
                headers=headers,
                data=file_content,
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.error(f"Tika server error: {response.status_code} - {response.text}")
                return False, {'error': f'Tika server returned status {response.status_code}'}

            # Extract content (plain text)
            content = response.text.strip()

            if not content:
                return False, {'error': 'No text content extracted'}

            # Get metadata separately
            metadata = self._get_metadata(file_content, filename)

            # Process and validate
            processed_metadata = self._process_metadata(metadata)
            validation_result = self._validate_extraction(content, processed_metadata)

            result = {
                'content': content,
                'metadata': processed_metadata,
                'validation': validation_result,
                'extraction_stats': {
                    'content_length': len(content),
                    'word_count': len(content.split()),
                    'line_count': len(content.splitlines()),
                    'metadata_fields': len(processed_metadata),
                }
            }

            print("result", result)

            logger.info(f"Successfully extracted content: {len(content)} characters")
            return True, result

        except requests.RequestException as e:
            logger.error(f"Tika server connection error: {e}")
            return False, {'error': f'Connection to Tika server failed: {str(e)}'}
        except Exception as e:
            logger.error(f"Tika extraction failed: {e}")
            return False, {'error': str(e)}

    def _get_metadata(self, file_content: bytes, filename: str = None) -> Dict:
        """
        Get metadata from Tika server

        Args:
            file_content: Document content as bytes
            filename: Original filename

        Returns:
            Dictionary with metadata
        """
        try:
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/octet-stream'
            }

            if filename:
                headers['Content-Disposition'] = f'attachment; filename="{filename}"'

            response = requests.put(
                f"{self.tika_server_url}/meta",
                headers=headers,
                data=file_content,
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Metadata extraction failed: {response.status_code}")
                return {}

        except Exception as e:
            logger.error(f"Metadata extraction error: {e}")
            return {}

    def extract_from_url(self, url: str) -> Tuple[bool, Dict]:
        """
        Extract content from a URL using Tika server

        Args:
            url: URL to extract content from

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Send URL to Tika for processing
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'text/plain'
            }

            response = requests.put(
                f"{self.tika_server_url}/tika",
                headers=headers,
                data=url.encode('utf-8'),
                timeout=self.timeout
            )

            if response.status_code != 200:
                return False, {'error': f'Tika server returned status {response.status_code}'}

            content = response.text.strip()

            if not content:
                return False, {'error': 'No text content extracted from URL'}

            # Get metadata for URL
            metadata = self._get_url_metadata(url)
            processed_metadata = self._process_metadata(metadata)
            validation_result = self._validate_extraction(content, processed_metadata)

            result = {
                'content': content,
                'metadata': processed_metadata,
                'validation': validation_result,
                'source_url': url,
                'extraction_stats': {
                    'content_length': len(content),
                    'word_count': len(content.split()),
                    'line_count': len(content.splitlines()),
                }
            }

            return True, result

        except Exception as e:
            logger.error(f"URL extraction failed: {e}")
            return False, {'error': str(e)}

    def _get_url_metadata(self, url: str) -> Dict:
        """Get metadata from URL using Tika"""
        try:
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'text/plain'
            }

            response = requests.put(
                f"{self.tika_server_url}/meta",
                headers=headers,
                data=url.encode('utf-8'),
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {}

        except Exception as e:
            logger.error(f"URL metadata extraction error: {e}")
            return {}

    def get_document_info(self, file_content: bytes, filename: str = None) -> Dict:
        """Get document information without full content extraction"""
        return self._get_metadata(file_content, filename)

    def get_supported_formats(self) -> list:
        """Get list of supported document formats from Tika server"""
        try:
            response = requests.get(
                f"{self.tika_server_url}/mime-types",
                headers={'Accept': 'application/json'},
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get supported formats: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error getting supported formats: {e}")
            return []

    def health_check(self) -> Dict:
        """Check Tika server health"""
        try:
            response = requests.get(
                f"{self.tika_server_url}/version",
                timeout=10
            )

            if response.status_code == 200:
                return {
                    'status': 'healthy',
                    'version': response.text.strip(),
                    'server_url': self.tika_server_url
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': f"HTTP {response.status_code}",
                    'server_url': self.tika_server_url
                }

        except Exception as e:
            return {
                'status': 'unreachable',
                'error': str(e),
                'server_url': self.tika_server_url
            }

    def _process_metadata(self, metadata: Dict) -> Dict:
        """
        Process and clean Tika metadata

        Args:
            metadata: Raw metadata from Tika

        Returns:
            Processed metadata dictionary
        """
        processed = {}

        # Standard metadata fields
        field_mapping = {
            'title': ['dc:title', 'Title'],
            'author': ['meta:author', 'Author', 'dc:creator'],
            'subject': ['dc:subject', 'Subject'],
            'keywords': ['meta:keyword', 'Keywords'],
            'creation_date': ['meta:creation-date', 'Creation-Date', 'dcterms:created'],
            'modified_date': ['meta:save-date', 'Last-Modified', 'dcterms:modified'],
            'content_type': ['Content-Type'],
            'language': ['meta:language', 'language'],
            'page_count': ['xmpTPg:NPages', 'meta:page-count'],
            'word_count': ['meta:word-count', 'Word-Count'],
            'character_count': ['meta:character-count', 'Character-Count'],
            'application': ['Application-Name', 'meta:app-name'],
            'producer': ['producer', 'Producer'],
        }

        # Map standard fields
        for key, possible_keys in field_mapping.items():
            for tika_key in possible_keys:
                if tika_key in metadata and metadata[tika_key]:
                    value = metadata[tika_key]
                    # Handle list values (take first item)
                    if isinstance(value, list) and value:
                        value = value[0]
                    processed[key] = value
                    break

        # Add all original metadata with tika_ prefix for reference
        for key, value in metadata.items():
            if key not in processed:
                # Clean key name
                clean_key = f"tika_{key.replace(':', '_').replace('-', '_').lower()}"
                processed[clean_key] = value

        return processed

    def _validate_extraction(self, content: str, metadata: Dict) -> Dict:
        """
        Validate the extraction quality

        Args:
            content: Extracted text content
            metadata: Extracted metadata

        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []

        # Check content quality
        if len(content) < 10:
            issues.append("Very short content extracted")

        # Check for garbled text (high ratio of non-alphanumeric characters)
        alphanumeric_ratio = sum(c.isalnum() or c.isspace() for c in content) / len(content) if content else 0
        if alphanumeric_ratio < 0.7:
            warnings.append("Potentially garbled text detected")

        # Check for repeated characters (OCR artifacts)
        import re
        repeated_chars = len(re.findall(r'(.)\1{5,}', content))
        if repeated_chars > 10:
            warnings.append("Multiple repeated character sequences found")

        # Check metadata completeness
        important_metadata = ['content_type', 'creation_date', 'page_count']
        missing_metadata = [field for field in important_metadata if not metadata.get(field)]
        if missing_metadata:
            warnings.append(f"Missing metadata: {', '.join(missing_metadata)}")

        return {
            'valid': len(issues) == 0,
            'quality_score': max(0, min(1, alphanumeric_ratio)),
            'issues': issues,
            'warnings': warnings,
        }
