import json

from django import forms
from django.core.exceptions import ValidationError

from .models import Document


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        # model = Document
        fields = ['title', 'document_type', 'file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter document title'
            }),
            'document_type': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
            'file': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'accept': '.pdf,.docx,.txt'
            })
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (10MB max)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError("File size cannot exceed 10MB")

            # Check file extension
            allowed_extensions = ['pdf', 'docx', 'txt']
            file_extension = file.name.split('.')[-1].lower()
            if file_extension not in allowed_extensions:
                raise forms.ValidationError(
                    f"File type '{file_extension}' not supported. "
                    f"Allowed types: {', '.join(allowed_extensions)}"
                )

        return file


class DocumentAdminForm(forms.ModelForm):
    file_upload = forms.FileField(
        required=False,
        help_text="Upload a new document file (PDF, DOC, DOCX, TXT, etc.)",
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf,.doc,.docx,.txt,.rtf,.odt'})
    )

    metadata_json = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 10, 'cols': 80, 'class': 'vLargeTextField'}),
        help_text="JSON metadata from document extraction (read-only)",
        label="Metadata (JSON)"
    )

    class Meta:
        model = Document
        fields = '__all__'
        widgets = {
            'extracted_text': forms.Textarea(attrs={'rows': 15, 'cols': 80}),
            'description': forms.Textarea(attrs={'rows': 4, 'cols': 80}),
            'error_message': forms.Textarea(attrs={'rows': 4, 'cols': 80, 'readonly': True}),
            'tags': forms.TextInput(attrs={'size': '80', 'placeholder': 'tag1, tag2, tag3'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate metadata_json field with pretty-printed JSON
        if self.instance and self.instance.extraction_metadata:
            self.fields['metadata_json'].initial = json.dumps(self.instance.extraction_metadata, indent=2)
            self.fields['metadata_json'].widget.attrs['readonly'] = True

        # Add help texts
        self.fields['tags'].help_text = "Enter tags separated by commas (e.g., 'academic, policy, student')"
        self.fields['source_url'].help_text = "Provide a URL to extract content from web pages or online documents"

    def clean_metadata_json(self):
        """Validate and parse metadata JSON"""
        metadata_json = self.cleaned_data.get('metadata_json')
        if metadata_json:
            try:
                parsed = json.loads(metadata_json)
                return parsed
            except json.JSONDecodeError:
                raise forms.ValidationError("Invalid JSON format")
        return {}

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Update metadata if metadata_json was provided
        metadata_json = self.cleaned_data.get('metadata_json')
        if metadata_json:
            instance.metadata = metadata_json

        if commit:
            instance.save()
        return instance
