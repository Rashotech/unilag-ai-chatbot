from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('admin/chatbot/document/<uuid:document_id>/download/', views.download_document, name='download_document'),

    # Chat
    path('', views.chat_view, name='chat_interface'),
    path('chat/', views.chat_interface, name='chat_interface'),

    path('send-message/', views.send_message, name='send_message'),
    path('rate-message/', views.rate_message, name='rate_message'),
    path('request-escalation/', views.request_escalation, name='request_escalation')
]