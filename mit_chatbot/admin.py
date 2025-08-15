import os

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .forms import DocumentAdminForm
from .models import *
from .services.firebase_service import FirebaseStorageService
from .services.tika_service import TikaExtractionService
from .tasks import process_document_tasks
from .services.typesense_service import TypesenseService

# Initialize services
firebase_service = FirebaseStorageService()
tika_service = TikaExtractionService()
search_service = TypesenseService()


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'first_name', 'last_name', 'user_type')


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'first_name', 'last_name', 'user_type', 'department', 'phone_number', 'is_active',
                  'is_staff')


@admin.register(CustomUser)
class UserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser

    list_display = ('email', 'first_name', 'last_name', 'user_type', 'department', 'is_active', 'is_staff',
                    'date_joined')
    list_filter = ('user_type', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name', 'department')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number', 'bio')}),
        ('Work info', {'fields': ('user_type', 'department')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Profile', {'fields': ('profile_picture', 'preferences')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'user_type', 'password1', 'password2'),
        }),
    )

    filter_horizontal = ()


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    form = DocumentAdminForm
    list_display = ('title', 'document_type', 'uploaded_by', 'processing_status', 'file_size_display', 'is_active',
                    'uploaded_at', 'actions_column')
    list_filter = ('document_type', 'processing_status', 'is_active', 'uploaded_at')
    search_fields = ('title', 'description', 'extracted_text')
    readonly_fields = ('id', 'uploaded_at', 'processed_at', 'file_size', 'extraction_stats_display', 'download_link')
    list_per_page = 25

    fieldsets = (
        ('Document Info', {
            'fields': ('title', 'description', 'document_type', 'tags', 'is_active')
        }),
        ('Upload', {
            'fields': ('file_upload', 'source_url'),
            'description': 'Upload a new file or provide a URL to extract content from.'
        }),
        ('Content', {
            'fields': ('extracted_text', 'metadata_json'),
            'classes': ('collapse',),
        }),
        ('Processing', {
            'fields': ('processing_status', 'error_message', 'extraction_stats_display'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('uploaded_by', 'uploaded_at', 'processed_at', 'file_size', 'download_link'),
            'classes': ('collapse',),
        }),
    )

    actions = ['reprocess_documents', 'activate_documents', 'deactivate_documents', 'update_search_index']

    def get_form(self, request, obj=None, **kwargs):
        """Pass current user to form"""
        form = super().get_form(request, obj, **kwargs)
        form.current_user = request.user
        return form

    def save_model(self, request, obj, form, change):
        """Handle file upload and processing in admin"""
        file_upload = form.cleaned_data.get('file_upload')
        source_url = form.cleaned_data.get('source_url')

        # Set uploaded_by if not set
        if not obj.uploaded_by:
            obj.uploaded_by = request.user

        # Save the basic object first
        super().save_model(request, obj, form, change)

        # Handle file upload
        if file_upload:
            try:
                obj.processing_status = 'processing'
                obj.save()

                # Reset file pointer to beginning
                file_upload.seek(0)

                # Upload to Firebase using the correct method
                firebase_success, firebase_path, firebase_metadata = firebase_service.upload_file(
                    file_upload,
                    filename=file_upload.name,
                    folder=obj.document_type
                )

                if firebase_success:
                    obj.firebase_path = firebase_path
                    obj.firebase_url = firebase_metadata.get('url', '')
                    obj.file_size = firebase_metadata.get('size', file_upload.size)

                    obj.save(update_fields=['firebase_path', 'firebase_url', 'file_size'])

                    # Queue processing task
                    # task = process_document_tasks.delay(str(obj.id), firebase_path)
                    # messages.success(request,
                    #                  f"Document '{obj.title}' uploaded. Processing in background (Task ID: {task.id})")


                    # Reset file pointer again for Tika extraction
                    file_upload.seek(0)
                    file_content = file_upload.read()

                    # Extract content using Tika
                    success, result = tika_service.extract_content(file_content, file_upload.name)

                    if success:
                        obj.extracted_text = result['content']
                        obj.extraction_metadata = result['metadata']
                        obj.processing_status = 'completed'
                        obj.processed_at = timezone.now()

                        # Update search index
                        search_service.index_document(obj)

                        messages.success(request, f"Document '{obj.title}' uploaded and processed successfully!")
                    else:
                        obj.error_message = result.get('error', 'Unknown extraction error')
                        obj.processing_status = 'failed'
                        messages.error(request, f"Content extraction failed: {obj.error_message}")
                else:
                    # firebase_path contains error message when firebase_success is False
                    obj.error_message = firebase_path
                    obj.processing_status = 'failed'
                    messages.error(request, f"File upload failed: {obj.error_message}")

                obj.save()

            except Exception as e:
                obj.processing_status = 'failed'
                obj.error_message = f"Upload error: {str(e)}"
                obj.save(update_fields=['processing_status', 'error_message'])
                messages.error(request, f"Upload failed: {str(e)}")

        # Handle URL extraction
        elif source_url:
            task = process_document_tasks.delay(str(obj.id), source_url=source_url)
            messages.success(request,
                             f"Document '{obj.title}' saved. Processing URL in background (Task ID: {task.id})")

    def file_size_display(self, obj):
        """Display file size in human readable format"""
        if obj.file_size:
            size = obj.file_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        return "-"

    file_size_display.short_description = "File Size"

    def extraction_stats_display(self, obj):
        """Display extraction statistics"""
        if obj.extracted_text:
            stats = {
                'Content Length': len(obj.extracted_text),
                'Word Count': len(obj.extracted_text.split()),
                'Line Count': len(obj.extracted_text.splitlines()),
                'Metadata Fields': len(obj.extraction_metadata) if obj.extraction_metadata else 0
            }
            return format_html(
                '<br>'.join([f"<strong>{k}:</strong> {v}" for k, v in stats.items()])
            )
        return "No content extracted"

    extraction_stats_display.short_description = "Extraction Stats"

    def download_link(self, obj):
        """Display download link for the document"""
        if obj.firebase_url:
            return format_html(
                '<a href="{}?download=1" target="_blank" class="button">Download File</a>',
                reverse('download_document', args=[obj.pk])
            )
        return "No file available"

    download_link.short_description = "Download"

    def actions_column(self, obj):
        """Display action buttons in list view"""
        actions = []
        if obj.processing_status == 'failed':
            actions.append(
                f'<a href="#" onclick="reprocessDocument({obj.pk})" class="button">Reprocess</a>'
            )
        if obj.firebase_url:
            actions.append(
                f'<a href="{reverse("download_document", args=[obj.pk])}?download=1" class="button">Download</a>'
            )
        return mark_safe(' '.join(actions)) if actions else "-"

    actions_column.short_description = "Actions"

    # Admin Actions
    def reprocess_documents(self, request, queryset):
        """Reprocess selected documents in background"""
        from .tasks import batch_reindex_documents_task

        document_ids = [str(doc.id) for doc in queryset]
        task = batch_reindex_documents_task.delay(document_ids)

        self.message_user(
            request,
            f"Queued {len(document_ids)} documents for reprocessing (Task ID: {task.id})"
        )

    reprocess_documents.short_description = "Reprocess selected documents"

    def activate_documents(self, request, queryset):
        """Activate selected documents"""
        count = queryset.update(is_active=True)
        self.message_user(request, f"Activated {count} documents.")

    activate_documents.short_description = "Activate selected documents"

    def deactivate_documents(self, request, queryset):
        """Deactivate selected documents"""
        count = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {count} documents.")

    deactivate_documents.short_description = "Deactivate selected documents"

    def update_search_index(self, request, queryset):
        """Update search index for selected documents in background"""
        from .tasks import index_document_task

        task_ids = []
        for document in queryset:
            if document.content and document.is_active:
                task = index_document_task.delay(str(document.id))
                task_ids.append(task.id)

        self.message_user(
            request,
            f"Queued {len(task_ids)} documents for indexing. Task IDs: {', '.join(task_ids[:5])}{'...' if len(task_ids) > 5 else ''}"
        )

    update_search_index.short_description = "Update search index"

    class Media:
        js = ('admin/js/document_admin.js',)
        css = {
            'all': ('admin/css/document_admin.css',)
        }


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_display', 'started_at', 'is_active', 'message_count')
    list_filter = ('is_active', 'started_at')
    search_fields = ('user__email', 'session_id')
    readonly_fields = ('id', 'started_at', 'ended_at')

    def user_display(self, obj):
        return obj.user.username if obj.user else f"Session: {obj.session_id}"

    user_display.short_description = "User"

    def message_count(self, obj):
        return obj.messages.count()

    message_count.short_description = "Messages"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation_snippet', 'message_type', 'content_preview', 'rating', 'timestamp')
    list_filter = ('message_type', 'rating', 'timestamp')
    search_fields = ('content',)
    readonly_fields = ('id', 'timestamp', 'response_time')

    def conversation_snippet(self, obj):
        user = obj.conversation.user
        if user:
            return f"{user.username} - {obj.conversation.started_at.strftime('%Y-%m-%d')}"
        return f"Session: {obj.conversation.session_id[:8]}..."

    conversation_snippet.short_description = "Conversation"

    def content_preview(self, obj):
        return obj.extracted_text[:100] + "..." if len(obj.extracted_text) > 100 else obj.extracted_text

    content_preview.short_description = "Content"


@admin.register(EscalationTicket)
class EscalationTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'status', 'priority', 'assigned_staff', 'created_at')
    list_filter = ('status', 'priority', 'created_at', 'assigned_staff')
    search_fields = ('subject', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        ('Ticket Information', {
            'fields': ('subject', 'description', 'status', 'priority', 'assigned_staff')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'resolved_at'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        })
    )


@admin.register(SystemAnalytics)
class SystemAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('date', 'total_conversations', 'total_messages',
                    'avg_response_time', 'user_satisfaction', 'escalation_rate')
    list_filter = ('date',)
    readonly_fields = ('date',)
    date_hierarchy = 'date'

    def avg_response_time(self, obj):
        return f"{obj.metrics.get('avg_response_time', 0):.2f}s"

    avg_response_time.short_description = "Avg Response Time"

    def user_satisfaction(self, obj):
        satisfaction = obj.metrics.get('user_satisfaction', 0)
        color = 'green' if satisfaction > 0.8 else 'orange' if satisfaction > 0.6 else 'red'
        return format_html(
            '<span style="color: {}">{:.1%}</span>',
            color,
            satisfaction
        )

    user_satisfaction.short_description = "User Satisfaction"

    def escalation_rate(self, obj):
        rate = obj.metrics.get('escalation_rate', 0)
        return f"{rate:.1%}"

    escalation_rate.short_description = "Escalation Rate"
