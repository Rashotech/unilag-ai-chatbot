from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
import traceback

from .models import Document
from .services.typesense_service import TypesenseService
from .services.tika_service import TikaExtractionService
from .services.firebase_service import FirebaseStorageService

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def index_document_task(self, document_id: str):
    """
    Background task to index a document in Typesense
    """
    try:
        logger.info(f"Starting indexing task for document: {document_id}")

        # Get document from database
        document = Document.objects.get(pk=document_id)

        if not document.extracted_text:
            logger.warning(f"Document {document_id} has no content to index")
            return {'status': 'skipped', 'reason': 'no_content'}

        # Initialize Typesense service
        typesense_service = TypesenseService()

        # Index the document
        success = typesense_service.index_document(document)

        if success:
            # Update document status
            document.vector_indexed = True
            document.index_version += 1
            document.save(update_fields=['vector_indexed', 'index_version'])

            logger.info(f"Successfully indexed document: {document_id}")
            return {
                'status': 'success',
                'document_id': document_id,
                'index_version': document.index_version
            }
        else:
            # Retry the task
            logger.error(f"Failed to index document: {document_id}")
            raise self.retry(countdown=60, exc=Exception("Indexing failed"))

    except Document.DoesNotExist:
        logger.error(f"Document not found: {document_id}")
        return {'status': 'error', 'reason': 'document_not_found'}

    except Exception as exc:
        logger.error(f"Error indexing document {document_id}: {exc}")
        logger.error(traceback.format_exc())

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries), exc=exc)

        # Mark document as failed after max retries
        try:
            document = Document.objects.get(pk=document_id)
            document.error_message = f"Indexing failed after {self.max_retries} retries: {str(exc)}"
            document.save(update_fields=['error_message'])
        except:
            pass

        return {'status': 'failed', 'error': str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_tasks(self, document_id: str, file_path: str = None, source_url: str = None):
    """
    Background task to process a document (extract content + index)
    """
    try:
        logger.info(f"Starting processing task for document: {document_id}")

        document = Document.objects.get(pk=document_id)
        document.processing_status = 'processing'
        document.save(update_fields=['processing_status'])

        # Initialize services
        tika_service = TikaExtractionService()
        firebase_service = FirebaseStorageService()

        success = False
        result = {}

        # Extract from file
        if file_path:
            # Download file from Firebase
            file_content = firebase_service.download_file(file_path)
            if file_content:
                success, result = tika_service.extract_content(file_content, file_path)
            else:
                result = {'error': 'Failed to download file from Firebase'}

        # Extract from URL
        elif source_url:
            success, result = tika_service.extract_from_url(source_url)

        if success:
            # Update document with extracted content
            document.extracted_text = result['content']
            document.extraction_metadata = result['metadata']
            document.processing_status = 'completed'
            document.processed_at = timezone.now()
            document.save(update_fields=['extracted_text', 'extraction_metadata', 'processing_status', 'processed_at'])

            # Queue indexing task
            index_document_task.delay(document_id)

            logger.info(f"Successfully processed document: {document_id}")
            return {
                'status': 'success',
                'document_id': document_id,
                'content_length': len(result['content']) if result['content'] else 0
            }
        else:
            # Update document with error
            error_msg = result.get('error', 'Unknown extraction error')
            document.error_message = error_msg
            document.processing_status = 'failed'
            document.save(update_fields=['error_message', 'processing_status'])

            logger.error(f"Failed to process document {document_id}: {error_msg}")
            return {'status': 'failed', 'error': error_msg}

    except Document.DoesNotExist:
        logger.error(f"Document not found: {document_id}")
        return {'status': 'error', 'reason': 'document_not_found'}

    except Exception as exc:
        logger.error(f"Error processing document {document_id}: {exc}")
        logger.error(traceback.format_exc())

        # Update document status
        try:
            document = Document.objects.get(pk=document_id)
            document.processing_status = 'failed'
            document.error_message = f"Processing failed: {str(exc)}"
            document.save(update_fields=['processing_status', 'error_message'])
        except:
            pass

        # Retry logic
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries), exc=exc)

        return {'status': 'failed', 'error': str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_tasks2(self, document_id: str, file_path: str = None, source_url: str = None):
    """
    Background task to process a document (extract content + index)
    """
    try:
        logger.info(f"Starting processing task for document: {document_id}")

        document = Document.objects.get(pk=document_id)
        document.processing_status = 'processing'
        document.save(update_fields=['processing_status'])

        # Initialize services
        # Initialize services
        # tika_service = TikaExtractionService()
        # firebase_service = FirebaseStorageService()

    except Document.DoesNotExist:
        logger.error(f"Document not found: {document_id}")
        return {'status': 'error', 'reason': 'document_not_found'}

    except Exception as exc:
        logger.error(f"Error processing document {document_id}: {exc}")
        logger.error(traceback.format_exc())

        # Update document status
        try:
            document = Document.objects.get(pk=document_id)
            document.processing_status = 'failed'
            document.error_message = f"Processing failed: {str(exc)}"
            document.save(update_fields=['processing_status', 'error_message'])
        except:
            pass

        # Retry logic
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries), exc=exc)

        return {'status': 'failed', 'error': str(exc)}

@shared_task(bind=True, max_retries=2)
def delete_document_from_index_task(self, document_id: str):
    """
    Background task to remove document from Typesense index
    """
    try:
        logger.info(f"Deleting document from index: {document_id}")

        typesense_service = TypesenseService()
        success = typesense_service.delete_document(document_id)

        if success:
            logger.info(f"Successfully deleted document from index: {document_id}")
            return {'status': 'success', 'document_id': document_id}
        else:
            logger.error(f"Failed to delete document from index: {document_id}")
            return {'status': 'failed', 'document_id': document_id}

    except Exception as exc:
        logger.error(f"Error deleting document from index {document_id}: {exc}")

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30, exc=exc)

        return {'status': 'failed', 'error': str(exc)}


@shared_task
def batch_reindex_documents_task(document_ids: list):
    """
    Background task to reindex multiple documents
    """
    results = []

    for doc_id in document_ids:
        try:
            result = index_document_task.delay(doc_id)
            results.append({'document_id': doc_id, 'task_id': result.id})
        except Exception as e:
            results.append({'document_id': doc_id, 'error': str(e)})

    return {
        'status': 'queued',
        'total_documents': len(document_ids),
        'results': results
    }


@shared_task
def cleanup_old_tasks_task():
    """
    Periodic task to cleanup old task results
    """
    from celery.result import AsyncResult
    from datetime import timedelta

    # This is a placeholder - implement based on your needs
    logger.info("Running cleanup task for old results")
    return {'status': 'completed', 'cleaned': 0}
