import logging
from typing import Tuple, Dict
from django.conf import settings
from django.utils import timezone
from .firebase_service import FirebaseStorageService
from .tika_service import TikaExtractionService
from ..models import Document
from .typesense_service import TypesenseService

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """Service for processing document uploads with Firebase and Tika"""

    def __init__(self):
        self.firebase_service = FirebaseStorageService()
        self.tika_service = TikaExtractionService()
        self.vector_service = TypesenseService()

    def process_document_upload(self, document_instance: Document, file_obj) -> Tuple[bool, str]:
        """
        Process a document upload: store in Firebase and extract content with Tika

        Args:
            document_instance: Document model instance
            file_obj: Django uploaded file object

        Returns:
            Tuple of (success, message)
        """
        try:
            # Update status
            document_instance.processing_status = 'processing'
            document_instance.save()

            # Step 1: Upload to Firebase
            success, file_path_or_error, metadata = self.firebase_service.upload_file(
                file_obj=file_obj,
                filename=f"{document_instance.id}_{file_obj.name}",
                folder=document_instance.document_type
            )

            if not success:
                document_instance.processing_status = 'failed'
                document_instance.error_message = f"Firebase upload failed: {file_path_or_error}"
                document_instance.save()
                return False, document_instance.error_message

            # Update document with Firebase info
            document_instance.firebase_path = file_path_or_error
            document_instance.firebase_url = metadata.get('url')
            document_instance.file_size = metadata.get('size', 0)
            document_instance.content_type = metadata.get('content_type')
            document_instance.save()

            # Step 2: Extract content with Tika
            file_obj.seek(0)  # Reset file pointer
            file_content = file_obj.read()

            extraction_success, extraction_result = self.tika_service.extract_content(
                file_content=file_content,
                filename=file_obj.name
            )

            if not extraction_success:
                document_instance.processing_status = 'failed'
                document_instance.error_message = f"Content extraction failed: {extraction_result.get('error')}"
                document_instance.save()
                return False, document_instance.error_message

            # Update document with extracted content
            document_instance.extracted_text = extraction_result['content']
            document_instance.extraction_metadata = {
                'tika_metadata': extraction_result['metadata'],
                'extraction_stats': extraction_result['extraction_stats'],
                'validation': extraction_result['validation']
            }

            # Step 3: Index in vector database
            try:
                index_success = self.vector_service.index_document(document_instance)
                if index_success:
                    document_instance.vector_indexed = True
                else:
                    logger.warning(f"Vector indexing failed for document {document_instance.id}")
            except Exception as e:
                logger.error(f"Vector indexing error: {e}")

            # Mark as completed
            document_instance.processing_status = 'completed'
            document_instance.processed_at = timezone.now()
            document_instance.save()

            logger.info(f"Successfully processed document {document_instance.id}")
            return True, "Document processed successfully"

        except Exception as e:
            document_instance.processing_status = 'failed'
            document_instance.error_message = str(e)
            document_instance.save()
            logger.error(f"Document processing failed: {e}")
            return False, str(e)

    def reprocess_document(self, document_instance: Document) -> Tuple[bool, str]:
        """
        Reprocess a document (re-extract content and re-index)

        Args:
            document_instance: Document model instance

        Returns:
            Tuple of (success, message)
        """
        try:
            if not document_instance.firebase_path:
                return False, "No Firebase path found for document"

            # Download from Firebase
            file_content = self.firebase_service.download_file(document_instance.firebase_path)
            if not file_content:
                return False, "Failed to download document from Firebase"

            # Re-extract content
            extraction_success, extraction_result = self.tika_service.extract_content(file_content)
            if not extraction_success:
                return False, f"Re-extraction failed: {extraction_result.get('error')}"

            # Update document
            document_instance.extracted_text = extraction_result['content']
            document_instance.extraction_metadata = {
                'tika_metadata': extraction_result['metadata'],
                'extraction_stats': extraction_result['extraction_stats'],
                'validation': extraction_result['validation']
            }

            # Re-index
            index_success = self.vector_service.index_document(document_instance)
            document_instance.vector_indexed = index_success
            document_instance.processing_status = 'completed'
            document_instance.save()

            return True, "Document reprocessed successfully"

        except Exception as e:
            logger.error(f"Document reprocessing failed: {e}")
            return False, str(e)

    def delete_document(self, document_instance: Document) -> Tuple[bool, str]:
        """
        Delete a document from Firebase and vector database

        Args:
            document_instance: Document model instance

        Returns:
            Tuple of (success, message)
        """
        try:
            # Delete from Firebase
            if document_instance.firebase_path:
                firebase_success = self.firebase_service.delete_file(document_instance.firebase_path)
                if not firebase_success:
                    logger.warning(f"Failed to delete from Firebase: {document_instance.firebase_path}")

            # Delete from vector database
            try:
                self.vector_service.delete_document(document_instance.id)
            except Exception as e:
                logger.warning(f"Failed to delete from vector database: {e}")

            # Delete from database
            document_instance.delete()

            return True, "Document deleted successfully"

        except Exception as e:
            logger.error(f"Document deletion failed: {e}")
            return False, str(e)

    def get_document_stats(self) -> Dict:
        """
        Get document processing statistics

        Returns:
            Dictionary with statistics
        """
        from django.db.models import Count, Q
        from django.utils import timezone
        from datetime import timedelta

        try:
            total_docs = Document.objects.count()
            processed_docs = Document.objects.filter(processing_status='completed').count()
            failed_docs = Document.objects.filter(processing_status='failed').count()
            pending_docs = Document.objects.filter(processing_status__in=['pending', 'processing']).count()

            # Recent uploads (last 7 days)
            week_ago = timezone.now() - timedelta(days=7)
            recent_uploads = Document.objects.filter(uploaded_at__gte=week_ago).count()

            # Document types
            doc_types = Document.objects.values('document_type').annotate(
                count=Count('id')
            ).order_by('-count')

            # Firebase storage stats
            firebase_stats = self.firebase_service.get_storage_usage()

            # Tika server health
            tika_health = self.tika_service.health_check()

            return {
                'total_documents': total_docs,
                'processed_documents': processed_docs,
                'failed_documents': failed_docs,
                'pending_documents': pending_docs,
                'recent_uploads': recent_uploads,
                'success_rate': (processed_docs / total_docs * 100) if total_docs > 0 else 0,
                'document_types': list(doc_types),
                'firebase_storage': firebase_stats,
                'tika_server': tika_health,
            }

        except Exception as e:
            logger.error(f"Error getting document stats: {e}")
            return {}

    def validate_file(self, file_obj) -> Tuple[bool, str]:
        """
        Validate uploaded file

        Args:
            file_obj: Django uploaded file object

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file size
        if file_obj.size > settings.MAX_UPLOAD_SIZE:
            max_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
            return False, f"File too large. Maximum size is {max_mb}MB"

        # Check file extension
        import os
        file_extension = os.path.splitext(file_obj.name)[1].lower().lstrip('.')
        if file_extension not in settings.ALLOWED_EXTENSIONS:
            return False, f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"

        # Check if file is not empty
        if file_obj.size == 0:
            return False, "File is empty"

        # Basic content validation
        try:
            file_obj.seek(0)
            first_bytes = file_obj.read(1024)
            file_obj.seek(0)

            # Check if file appears to be binary (for common document types)
            if file_extension == 'txt' and b'\x00' in first_bytes:
                return False, "Text file appears to contain binary data"

        except Exception as e:
            return False, f"Error reading file: {e}"

        return True, "File is valid"
