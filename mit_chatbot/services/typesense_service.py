import logging
import re

import requests
import typesense
from typing import List, Dict, Optional
from django.conf import settings
import hashlib

logger = logging.getLogger(__name__)


class TypesenseService:
    """Service for managing Typesense search operations"""

    def __init__(self):
        self.client = typesense.Client(settings.TYPESENSE_CONFIG)
        self.base_url = f"{settings.TYPESENSE_PROTOCOL}://{settings.TYPESENSE_HOST}:{settings.TYPESENSE_PORT}"
        self.api_key = settings.TYPESENSE_API_KEY
        self.headers = {
            'X-TYPESENSE-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

        self.collection_name = 'university_documents'
        self.conversation_collection = 'conversation_store'
        self.conversation_model = '5a660314-d51d-4f6e-89e9-5a2aa4ee5854'

        self._ensure_collection_exists()
        self._setup_conversation_collection()

    def _ensure_collection_exists(self):
        """Create collection if it doesn't exist"""
        try:
            self.client.collections[self.collection_name].retrieve()
        except typesense.exceptions.ObjectNotFound:
            schema = {
                'name': self.collection_name,
                'fields': [
                    {'name': 'id', 'type': 'string'},
                    {'name': 'title', 'type': 'string'},
                    {'name': 'content', 'type': 'string'},
                    {'name': 'document_type', 'type': 'string', 'facet': True},
                    {'name': 'document_id', 'type': 'string'},
                    {'name': 'chunk_id', 'type': 'int32'},
                    # {
                    #     'name': 'embedding',
                    #     'type': 'float[]',
                    #     'num_dim': 768
                    # },
                    {
                        "name": "embedding",
                        "type": "float[]",
                        "embed": {
                            "from": [
                                "content",
                            ],
                            "model_config": {
                                "model_name": "ts/all-MiniLM-L12-v2"
                            }
                        }
                    },
                    {'name': 'created_at', 'type': 'int64'},
                ]
            }
            self.client.collections.create(schema)

    def _setup_conversation_collection(self):
        """Setup conversation history collection (required schema)"""
        schema = {
            'name': self.conversation_collection,
            'fields': [
                {'name': 'model_id', 'type': 'string'},
                {'name': 'conversation_id', 'type': 'string'},
                {'name': 'role', 'type': 'string', "index": False },
                {'name': 'message', 'type': 'string', "index": False },
                {'name': 'timestamp', 'type': 'int32'}
            ]
        }

        try:
            self.client.collections[self.conversation_collection].retrieve()
            # results = self._setup_conversation_model()
            # print("results", results)
        except typesense.exceptions.ObjectNotFound:
            self.client.collections.create(schema)

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None,
                      params: Optional[Dict] = None) -> Dict:
        """Make HTTP request to Typesense API"""
        try:
            url = f"{self.base_url}{endpoint}"

            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data if data else None,
                params=params if params else None,
                timeout=300
            )

            if response.status_code in [200, 201]:
                return {'success': True, 'data': response.json()}
            else:
                logger.error(f"Typesense API error: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"API error: {response.status_code}",
                    'details': response.text
                }

        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            return {'success': False, 'error': f"Request failed: {str(e)}"}

    def _setup_conversation_model(self):
        """Create conversation model via API"""
        model_config = {
            'id': self.conversation_model,
            'model_name': 'gcp/gemini-2.0-flash',
            'api_key': settings.GOOGLE_API_KEY,
            'max_bytes': 16384,
            'history_collection': self.conversation_collection,
            'system_prompt': """You are UNILAG Assistant, the official AI helper for University of Lagos students, staff, and prospective applicants.

CORE IDENTITY:
- Authoritative source for UNILAG information
- Comprehensive knowledge spanning academics, administration, and campus life
- Always current, helpful, and action-oriented

KNOWLEDGE SCOPE:
✓ Complete UNILAG academic programs and requirements
✓ Admission processes (UTME, Direct Entry, Postgraduate)
✓ Student services, facilities, and campus resources
✓ Administrative procedures and policies
✓ Online portals and digital services
✓ Department contacts and locations
✓ Fees, scholarships, and financial information
✓ Campus events and activities

KEY UNILAG RESOURCES:
• Main Site: unilag.edu.ng
• Student Portal: stu.unilag.edu.ng  
• E-Learning: elearn.unilag.edu.ng
• Library: library.unilag.edu.ng
• Location: Akoka, Lagos (Main) | Idi-Araba (Medicine)

ESSENTIAL CONTACTS:
• Registry: registry@unilag.edu.ng | +234-1-7749-309
• Student Affairs: studentaffairs@unilag.edu.ng
• ICT Support: ict@unilag.edu.ng
• Bursary: bursary@unilag.edu.ng
 Guidelines:
    - Always be professional, helpful, and concise
    - Base your answers on the provided context
    - If information is not in the context, politely say so and suggest contacting the relevant department
    - Provide specific details when available (dates, requirements, contact information)
    - Direct students to official resources when appropriate
    - Be encouraging and supportive in your tone

    If you cannot find relevant information in the provided context, respond with: "I don't have specific information about that in my current knowledge base. I recommend contacting [relevant department] directly for the most accurate and up-to-date information.
RESPONSE STANDARDS:
1. Direct, confident answers without disclaimers about knowledge limitations
2. Include specific contacts, websites, or next steps
3. Structure information clearly with headers and bullets
4. Provide comprehensive guidance for complex procedures
5. Offer alternative solutions and backup resources
6. Use authoritative, helpful tone throughout"""
        }

        # Create new model
        return self._make_request('POST', '/conversations/models', model_config)

    def conversational_search(
            self,
            query: str,
            conversation_id: Optional[str] = None,
            user_id: Optional[str] = None,
            stream: bool = False
    ) -> Dict:
        """Perform conversational search via API"""
        try:
            # Prepare search parameters
            search_params = {
                'searches': [{
                    'collection': self.collection_name,
                    "query_by": "embedding",
                    "exclude_fields": "embedding",
                }]
            }

            # Make the conversational search request
            endpoint = f'/multi_search?q={query}&conversation=true&conversation_model_id={self.conversation_model}'
            if conversation_id:
                endpoint = endpoint + f'&conversation_id={conversation_id}'
            result = self._make_request('POST', endpoint, search_params)

            if result['success']:
                response_data = result['data']
                search_results = response_data.get('results', [{}])[0]
                conversation_data = response_data.get('conversation', {})

                return {
                    'success': True,
                    'conversation_id': conversation_data.get('conversation_id', ''),
                    'answer': conversation_data.get('answer', ''),
                    'query': query,
                    'sources': self._extract_sources(search_results),
                    'conversation': conversation_data
                }
            else:
                return result

        except Exception as e:
            logger.error(f"Error in conversational search: {e}")
            return {
                'success': False,
                'error': str(e),
                'conversation_id': conversation_id or 'unknown'
            }

    def _extract_sources(self, search_result: Dict) -> List[Dict]:
        """Extract unique source information from search results"""
        sources = []
        seen_documents = set()
        hits = search_result.get('hits', [])

        for hit in hits:
            document = hit.get('document', {})
            document_id = document.get('document_id')

            # Skip if we've already seen this document
            if document_id in seen_documents:
                continue

            seen_documents.add(document_id)

            sources.append({
                'document_id': document_id,
                'title': document.get('title'),
                'content_snippet': document.get('content', '')[:200] + '...' if document.get('content') else '',
                'chunk_index': document.get('chunk_index'),
                'relevance_score': hit.get('text_match', 0)
            })

            # Limit to top 5 unique documents
            if len(sources) >= 5:
                break

        return sources

    def get_conversation_history(self, conversation_id: str) -> Dict:
        """Get conversation history"""
        try:
            search_result = self.client.collections[self.conversation_collection].documents.search({
                'q': '*',
                'filter_by': f'conversation_id:={conversation_id}',
                'sort_by': 'timestamp:asc',
                'per_page': 100
            })

            messages = []
            for hit in search_result['hits']:
                doc = hit['document']
                messages.append({
                    'role': doc['role'],
                    'message': doc['message'],
                    'timestamp': doc['timestamp']
                })

            return {
                'success': True,
                'conversation_id': conversation_id,
                'messages': messages
            }

        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return {'success': False, 'error': str(e)}

    def index_document(self, document) -> bool:
        """Index document chunks in Typesense"""
        # doc_id: str, title: str, content: str,
        # document_type: str, chunks: List[Dict]
        try:
            document_id = str(document.id)
            document_title = document.title
            document_type = document.document_type

            print("document_id", document_id)
            chunks =  self.smart_chunk_text(document.extracted_text)

            if not chunks:
                print(f"No chunks generated for document {document_id}")
                return False

            documents = []
            print("chunks length", len(chunks))

            for chunk in chunks:
                # Generate embedding (truncated to avoid URL length issues)
                # full_embedding = self.encoder.encode([chunk['content']])[0].tolist()
                # embedding = full_embedding  # Use first 100 dimensions

                # Create unique ID for chunk
                chunk_hash = hashlib.md5(
                    f"{document_id}_{chunk['chunk_id']}".encode()
                ).hexdigest()

                document = {
                    'id': chunk_hash,
                    'title': document_title,
                    'content': chunk['content'],
                    'document_type': document_type,
                    'document_id': document_id,
                    'chunk_id': chunk['chunk_id'],
                    'created_at': int(chunk.get('timestamp', 0))
                }
                documents.append(document)

            if not documents:
                print(f"No valid documents to index for {document_id}")
                return False

            # Batch import
            import_response = self.client.collections[self.collection_name].documents.import_(
                documents, {'action': 'upsert'}, batch_size=100
            )

            successful_imports = sum(1 for item in import_response if item.get('success', False))
            total_chunks = len(documents)

            print(f"Indexed {successful_imports}/{total_chunks} chunks for document {document_id}")

            # return True
            return all(item.get('success', False) for item in import_response)

        except Exception as e:
            print(f"Error indexing document in Typesense: {e}")
            return False

    def delete_document(self, doc_id: str) -> bool:
        """Delete all chunks of a document"""
        try:
            delete_params = {
                'filter_by': f'document_id:={doc_id}'
            }

            self.client.collections[self.collection_name].documents.delete(delete_params)
            return True

        except Exception as e:
            print(f"Error deleting document from Typesense: {e}")
            return False

    def smart_chunk_text(self, text: str, chunk_size: int = 1500, overlap: int = 200) -> List[Dict]:
        """Smart chunking that preserves sentence boundaries"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        current_size = 0

        for sentence in sentences:
            sentence_size = len(sentence)

            if current_size + sentence_size > chunk_size and current_chunk:
                chunks.append({
                    'content': current_chunk.strip(),
                    'size': current_size,
                    'chunk_id': len(chunks)
                })

                # Handle overlap
                if overlap > 0:
                    words = current_chunk.split()
                    overlap_words = words[-overlap:] if len(words) > overlap else words
                    current_chunk = " ".join(overlap_words) + " " + sentence
                    current_size = len(current_chunk)
                else:
                    current_chunk = sentence
                    current_size = sentence_size
            else:
                current_chunk += (" " if current_chunk else "") + sentence
                current_size += sentence_size + (1 if current_chunk else 0)

        if current_chunk.strip():
            chunks.append({
                'content': current_chunk.strip(),
                'size': current_size,
                'chunk_id': len(chunks)
            })

        return chunks