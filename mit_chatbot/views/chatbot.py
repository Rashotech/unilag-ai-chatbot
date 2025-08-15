import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import time

from mit_chatbot.models import *
from mit_chatbot.services.langchain_service import LangChainService

from datetime import timedelta
import json

from ..services.document_service import DocumentProcessingService
from ..services.enhanced_langchain_service import EnhancedLangChainService
from ..services.firebase_service import FirebaseStorageService
from ..services.tika_service import TikaExtractionService

logger = logging.getLogger(__name__)

# Initialize services
langchain_service = LangChainService()
enhanced_langchain_service = EnhancedLangChainService()
document_service = DocumentProcessingService()
firebase_service = FirebaseStorageService()
tika_service = TikaExtractionService()


def home_view(request):
    """Home page - redirect to chat"""
    return redirect('chat')


def chat_view(request):
    """Main chat interface"""
    # Get or create conversation
    conversation_id = None
    conversation = None

    if request.user.id:
        try:
            conversation = Conversation.objects.get(user=request.user)
            if conversation.session_id:
                conversation_id = conversation.session_id
        except Conversation.DoesNotExist:
            conversation = None

    if not conversation:
        conversation = Conversation.objects.create(
            user=request.user if request.user.is_authenticated else None,
        )

    # Get conversation messages
    messages = conversation.messages.all().order_by('timestamp')

    # Get analytics for popular questions (for suggestions)
    popular_topics = []

    context = {
        'conversation': conversation,
        'conversation_id': conversation_id,
        'chat_messages': messages,
        'popular_topics': popular_topics[:5],
        'user_context': get_user_context(request.user) if request.user.is_authenticated else None
    }

    return render(request, 'chatbot/chat.html', context)


@login_required
def chat_interface(request):
    conversation_id = request.session.get('conversation_id', None)
    conversations = Conversation.objects.filter(user=request.user).order_by('-started_at')
    current_conversation = conversations.first()

    messages = []
    if current_conversation:
        messages = current_conversation.messages.order_by('timestamp')

    popular_topics = []

    context = {
        'chat_messages': messages,
        'conversation': current_conversation,
        'conversation_id': conversation_id,
        'popular_topics': popular_topics[:5],  # Top 5 popular topics
        'user_context': get_user_context(request.user) if request.user.is_authenticated else None
    }

    return render(request, 'chatbot/chat.html', context)


def get_user_context(user):
    """Get comprehensive user context"""
    if not user or not user.is_authenticated:
        return None

    context = {
        'authenticated': True,
        'user_id': user.id,
        'name': user.get_full_name(),
        'email': user.email,
        'user_type': user.user_type
    }

    if hasattr(user, 'student_profile'):
        student = user.student_profile
        context.update({
            'student_id': student.student_id,
            'department': student.department.name,
            'faculty': student.department.faculty.name,
            'current_level': student.current_level,
            'cgpa': float(student.current_cgpa) if student.current_cgpa else 0.0,
            'entry_year': student.entry_session.name if student.entry_session else None,
            'status': student.status,
            'current_courses_count': 3,
            'total_credits': student.results.filter(
                is_final=True,
                grade_point__gt=0
            ).aggregate(total=models.Sum('course__credits'))['total'] or 0
        })

    return context


@csrf_exempt
@require_http_methods(["POST"])
def rate_message(request):
    """Rate a bot message"""
    try:
        data = json.loads(request.body)
        message_id = data.get('message_id')
        rating = data.get('rating')  # 1 or 2

        if not message_id or rating not in [1, 2]:
            return JsonResponse({'error': 'Invalid data'}, status=400)

        message = get_object_or_404(Message, id=message_id, message_type='bot')
        message.rating = rating
        message.save()

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
def request_escalation(request):
    """Request human escalation"""
    try:
        conversation_id = request.session.get('conversation_id')
        if not conversation_id:
            return JsonResponse({'error': 'No conversation found'}, status=404)

        conversation = get_object_or_404(Conversation, id=conversation_id)

        # Check if escalation already exists
        existing_ticket = EscalationTicket.objects.filter(
            conversation=conversation,
            status__in=['new', 'assigned', 'in_progress']
        ).first()

        if existing_ticket:
            return JsonResponse({
                'success': True,
                'message': 'Your request has already been escalated. A staff member will contact you soon.',
                'ticket_id': str(existing_ticket.id)
            })

        # Create new escalation ticket
        latest_message = conversation.messages.filter(message_type='user').last()
        subject = latest_message.content[:50] + "..." if latest_message else "User requested human assistance"

        ticket = EscalationTicket.objects.create(
            conversation=conversation,
            subject=subject,
            description=f"User requested human escalation.\nLatest query: {latest_message.content if latest_message else 'N/A'}",
            priority='medium'
        )

        return JsonResponse({
            'success': True,
            'message': 'Your request has been escalated to our support team. Someone will contact you shortly.',
            'ticket_id': str(ticket.id)
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_popular_topics(days=7, limit=10):
    """Get popular topics from recent conversations"""
    cutoff_date = timezone.now() - timedelta(days=days)

    # Get recent user messages
    recent_messages = Message.objects.filter(
        message_type='user',
        timestamp__gte=cutoff_date
    ).values('content')

    # Simple keyword extraction (in production, use proper NLP)
    topics = {}
    common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}

    for msg in recent_messages:
        words = msg['content'].lower().split()
        for word in words:
            word = word.strip('.,!?')
            if len(word) > 3 and word not in common_words:
                topics[word] = topics.get(word, 0) + 1

    # Return top topics
    return sorted(topics.items(), key=lambda x: x[1], reverse=True)[:limit]

@csrf_exempt
@require_http_methods(["POST"])
def rate_message(request):
    """Handle message rating"""
    try:
        data = json.loads(request.body)
        message_id = data.get('message_id')
        rating = data.get('rating')  # 1 for thumbs down, 2 for thumbs up

        message = get_object_or_404(Message, id=message_id)
        message.rating = rating
        message.save()

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def escalate_conversation(request):
    """Escalate conversation to human support"""
    try:
        data = json.loads(request.body)
        department = data.get('department', 'General Support')

        session_id = request.session.get('conversation_id')
        conversation = get_object_or_404(Conversation, session_id=session_id, is_active=True)

        # Create escalation ticket
        ticket = EscalationTicket.objects.create(
            conversation=conversation,
            department=department
        )

        # Add system message
        Message.objects.create(
            conversation=conversation,
            message_type='system',
            content=f"Your query has been escalated to {department}. Ticket ID: {ticket.id}"
        )

        return JsonResponse({
            'success': True,
            'ticket_id': str(ticket.id),
            'message': 'Your query has been escalated to our support team.'
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def send_message_main(request):
    """Handle chat messages via AJAX with Typesense conversational search"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()

        if not user_message:
            return JsonResponse({'error': 'Empty message'}, status=400)

        # Record start time for response time tracking
        start_time = time.time()

        # Get or create conversation with proper session/user handling
        conversation = _get_or_create_conversation(request, data)

        # Save user message
        user_msg = Message.objects.create(
            conversation=conversation,
            message_type='user',
            content=user_message
        )

        # Use the conversation's typesense_conversation_id for continuity
        typesense_conversation_id = conversation.metadata.get('typesense_conversation_id')

        # Process with LangChain service (which uses Typesense RAG)
        result = langchain_service.process_conversation(
            query=user_message,
            conversation_id=typesense_conversation_id,
            user_id=str(request.user.id) if request.user.is_authenticated else None
        )

        # Calculate response time
        response_time = time.time() - start_time

        if result['success']:
            # Update conversation with Typesense conversation ID for future continuity
            new_typesense_id = result.get('conversation_id')
            if new_typesense_id and new_typesense_id != typesense_conversation_id:
                conversation.metadata['typesense_conversation_id'] = new_typesense_id
                conversation.save()

            # Save bot response with enhanced metadata
            bot_message = Message.objects.create(
                conversation=conversation,
                message_type='bot',
                content=result['response'],
                metadata={
                    'typesense_conversation_id': new_typesense_id,
                    'escalation_needed': result.get('escalation_needed', False),
                    'sources_count': len(result.get('sources', [])),
                    'typesense_success': True,
                    'search_time_ms': result.get('typesense_data', {}).get('search_time_ms'),
                    'context_used': bool(result.get('sources'))
                },
                response_time=response_time
            )

            # Save source documents from Typesense results
            _save_message_sources(bot_message, result.get('sources', []))

            # Handle escalation if needed
            if result.get('escalation_needed'):
                _create_escalation_ticket(conversation, user_message, result['response'])

            return JsonResponse({
                'success': True,
                'response': result['response'],
                'message_id': str(bot_message.id),
                'conversation_id': str(conversation.id),
                'typesense_conversation_id': new_typesense_id,
                'sources': _format_sources_for_frontend(result.get('sources', [])),
                'escalation_available': result.get('escalation_needed', False),
                'response_time': round(response_time, 2),
                'context_used': len(result.get('sources', [])) > 0,
                'conversation_history_available': bool(new_typesense_id)
            })
        else:
            # Handle error case
            error_response = result.get('response', 'I apologize, but I encountered an error. Please try again.')

            bot_message = Message.objects.create(
                conversation=conversation,
                message_type='bot',
                content=error_response,
                metadata={
                    'error': result.get('error', ''),
                    'success': False,
                    'typesense_conversation_id': result.get('conversation_id')
                },
                response_time=response_time
            )

            # Still create escalation for errors
            _create_escalation_ticket(conversation, user_message, error_response, priority='high')

            return JsonResponse({
                'success': True,  # Frontend success, but with error content
                'response': error_response,
                'message_id': str(bot_message.id),
                'conversation_id': str(conversation.id),
                'error': True,
                'escalation_available': True
            })

    except Exception as e:
        logger.error(f"Error in send_message: {e}", exc_info=True)
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def send_message(request):
    """Handle chat messages via AJAX with Typesense conversational search"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')

        if not user_message:
            return JsonResponse({'error': 'Empty message'}, status=400)

        # Record start time for response time tracking
        start_time = time.time()

        # Get or create conversation with proper session/user handling
        conversation = _get_or_create_conversation(request, data)

        # Save user message
        user_msg = Message.objects.create(
            conversation=conversation,
            message_type='user',
            content=user_message
        )

        # Use the conversation's typesense_conversation_id for continuity
        typesense_conversation_id = conversation.metadata.get('typesense_conversation_id')

        user_context = get_user_context(request.user)

        # Process with LangChain service (which uses Typesense RAG)
        result = enhanced_langchain_service.process_query(
            query=user_message,
            conversation_id=conversation_id or typesense_conversation_id,
            user_context=user_context
        )

        # Calculate response time
        response_time = time.time() - start_time

        if result['success']:
            # Update conversation with Typesense conversation ID for future continuity
            new_typesense_id = result.get('conversation_id')
            if new_typesense_id and new_typesense_id != typesense_conversation_id:
                conversation.session_id = new_typesense_id
                conversation.metadata['typesense_conversation_id'] = new_typesense_id
                conversation.save()

            # Save bot response with enhanced metadata
            bot_message = Message.objects.create(
                conversation=conversation,
                message_type='bot',
                content=result['response'],
                metadata={
                    'typesense_conversation_id': new_typesense_id,
                    'escalation_needed': result.get('escalation_needed', False),
                    'sources_count': len(result.get('sources', [])),
                    'typesense_success': True,
                    'search_time_ms': result.get('typesense_data', {}).get('search_time_ms'),
                    'context_used': bool(result.get('sources'))
                },
                response_time=response_time
            )

            # Save source documents from Typesense results
            _save_message_sources(bot_message, result.get('sources', []))

            # Handle escalation if needed
            if result.get('escalation_needed'):
                _create_escalation_ticket(conversation, user_message, result['response'])

            return JsonResponse({
                'success': True,
                'response': result['response'],
                'message_id': str(bot_message.id),
                'conversation_id': new_typesense_id,
                'typesense_conversation_id': new_typesense_id,
                'sources': _format_sources_for_frontend(result.get('sources', [])),
                'escalation_available': result.get('escalation_needed', False),
                'response_time': round(response_time, 2),
                'context_used': len(result.get('sources', [])) > 0,
                'conversation_history_available': bool(new_typesense_id)
            })
        else:
            # Handle error case
            error_response = result.get('response', 'I apologize, but I encountered an error. Please try again.')

            bot_message = Message.objects.create(
                conversation=conversation,
                message_type='bot',
                content=error_response,
                metadata={
                    'error': result.get('error', ''),
                    'success': False,
                    'typesense_conversation_id': result.get('conversation_id')
                },
                response_time=response_time
            )

            # Still create escalation for errors
            _create_escalation_ticket(conversation, user_message, error_response, priority='high')

            return JsonResponse({
                'success': True,  # Frontend success, but with error content
                'response': error_response,
                'message_id': str(bot_message.id),
                'conversation_id': str(conversation.id),
                'error': True,
                'escalation_available': True
            })

    except Exception as e:
        logger.error(f"Error in send_message: {e}", exc_info=True)
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)


def _get_or_create_conversation(request, data):
    """Get existing conversation or create new one with proper ID tracking"""
    # Try to get existing conversation ID from request
    conversation_id = data.get('conversation_id')

    if conversation_id:
        try:
            # Try to get existing conversation
            conversation = Conversation.objects.get(session_id=conversation_id)

            # Verify ownership for authenticated users
            if request.user.is_authenticated and conversation.user != request.user:
                # Create new conversation if ownership doesn't match
                conversation = _create_new_conversation(request)

            return conversation
        except Conversation.DoesNotExist:
            # Conversation doesn't exist, create new one
            pass

    # Create new conversation
    return _create_new_conversation(request)


def _create_new_conversation(request):
    """Create a new conversation"""
    return Conversation.objects.create(
        user=request.user if request.user.is_authenticated else None,
        # session_id=request.session.session_key or request.session._get_or_create_session_key(),
        metadata={'typesense_conversation_id': None}  # Will be populated after first Typesense call
    )


def _save_message_sources(message, sources):
    """Save source documents from Typesense results"""
    for i, source in enumerate(sources[:5]):  # Limit to top 5 sources
        try:
            # Try to find the document by ID
            document_id = source.get('document_id')
            if document_id:
                try:
                    document = Document.objects.get(id=document_id)
                    MessageSource.objects.create(
                        message=message,
                        document=document,
                        relevance_score=source.get('relevance_score', 0.0),
                        chunk_content=source.get('content_snippet', '')[:1000],
                    )
                except Document.DoesNotExist:
                    logger.warning(f"Document {document_id} not found in database")
                    continue
        except Exception as e:
            logger.error(f"Error saving message source: {e}")
            continue


def _create_escalation_ticket(conversation, user_message, bot_response, priority='medium'):
    """Create escalation ticket for human intervention"""
    try:
        EscalationTicket.objects.create(
            conversation=conversation,
            subject=f"Query requiring assistance: {user_message[:50]}...",
            description=f"User Query: {user_message}\n\nBot Response: {bot_response}",
            priority=priority
        )
    except Exception as e:
        logger.error(f"Error creating escalation ticket: {e}")


def _format_sources_for_frontend(sources):
    """Format sources for frontend display"""
    formatted_sources = []

    for source in sources[:3]:  # Top 3 sources for frontend
        formatted_sources.append({
            'title': source.get('title', 'Untitled Document'),
            'snippet': source.get('content_snippet', ''),
            'document_type': source.get('file_type', 'document'),
            'category': source.get('category', 'general'),
            'relevance': round(source.get('relevance_score', 0.0), 2),
            'chunk_index': source.get('chunk_index', 0)
        })

    return formatted_sources


def custom_login(request):
    """Login view for students using student_id and password"""
    if request.user.is_authenticated:
        return redirect('chat_interface')

    if request.method == 'POST':
        student_id = request.POST.get('student_id', '').strip()
        password = request.POST.get('password', '').strip()
        remember_me = request.POST.get('remember_me')

        if not student_id or not password:
            messages.error(request, 'Please provide both Matric Number and Password.')
            return render(request, 'login.html')

        try:
            # Find student by student_id
            student = Student.objects.select_related(
                'user',
                'faculty',
                'department',
                'current_session',
                'entry_session'
            ).get(student_id=student_id)

            user = student.user

            # Check if user is active
            if not user.is_active or not student.is_active:
                messages.error(request, 'Your account is not active. Please contact administration.')
                logger.warning(f"Inactive user/student attempted login: {student_id}")
                return render(request, 'login.html')

            # Check password
            if user.check_password(password):
                # Login the user
                login(request, user)

                # Handle remember me
                if not remember_me:
                    request.session.set_expiry(0)  # Session expires when browser closes
                else:
                    request.session.set_expiry(1209600)  # 2 weeks

                # Store student info in session for quick access
                request.session['student_data'] = {
                    'student_id': student.student_id,
                    'full_name': student.full_name,
                    'faculty': student.faculty.name,
                    'department': student.department.name,
                    'current_level': student.current_level,
                    'cgpa': float(student.current_cgpa),
                    'academic_standing': student.get_academic_standing_display(),
                    'status': student.get_status_display(),
                }

                logger.info(f"Student {student_id} logged in successfully")
                messages.success(
                    request,
                    f'Welcome back, {student.full_name}! 🎓'
                )

                # Redirect to chat interface
                next_url = request.GET.get('next', 'chat_interface')
                return redirect(next_url)

            else:
                messages.error(request, 'Invalid password. Please check your credentials.')
                logger.warning(f"Invalid password attempt for student: {student_id}")

        except Student.DoesNotExist:
            messages.error(request, f'Invalid Credentials')
            logger.warning(f"Student not found: {student_id}")

        except Exception as e:
            logger.error(f"Login error for student {student_id}: {e}")
            messages.error(request, 'An error occurred during login. Please try again.')

    return render(request, 'login.html')


def custom_logout(request):
    """Custom logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

