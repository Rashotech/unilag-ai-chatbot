from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('send-message/', views.send_message, name='send_message'),
    path('rate-message/', views.rate_message, name='rate_message'),
    path('request-escalation/', views.request_escalation, name='request_escalation'),

    # Admin URLs
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('document-management/', views.document_management, name='document_management'),
    path('delete-document/<uuid:document_id>/', views.delete_document, name='delete_document'),
    path('download-document/<uuid:document_id>/', views.download_document, name='download_document'),
    path('api/send-message/', views.send_message, name='send_message'),
    path('api/rate-message/', views.rate_message, name='rate_message'),
    path('api/escalate/', views.escalate_conversation, name='escalate'),

    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # path('register/', views.register_view, name='register'),

    # Admin URLs (require staff permissions)
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('documents/', views.document_management, name='document_management'),
    path('conversations/', views.conversation_logs, name='conversation_logs'),
    path('escalations/', views.escalation_queue, name='escalation_queue'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('users/', views.user_management, name='user_management'),
    path('settings/', views.system_settings, name='system_settings'),

    # AJAX endpoints
    path('api/upload-document/', views.upload_document, name='upload_document'),
    path('api/toggle-document/<uuid:doc_id>/', views.toggle_document_status, name='toggle_document_status'),
    path('api/delete-document/<uuid:doc_id>/', views.delete_document, name='delete_document'),
    path('api/assign-ticket/<uuid:ticket_id>/', views.assign_ticket, name='assign_ticket'),
    path('api/update-ticket/<uuid:ticket_id>/', views.update_ticket, name='update_ticket'),
    path('api/system-health/', views.system_health_check, name='system_health'),
]