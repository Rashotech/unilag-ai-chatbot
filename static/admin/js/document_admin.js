// Enhanced admin functionality for documents
function reprocessDocument(documentId) {
    if (confirm('Are you sure you want to reprocess this document?')) {
        fetch(`/admin/chatbot/document/${documentId}/reprocess/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Error: ' + data.error);
            }
        });
    }
}

// Auto-populate title from filename
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.querySelector('#id_file_upload');
    const titleInput = document.querySelector('#id_title');

    if (fileInput && titleInput) {
        fileInput.addEventListener('change', function() {
            if (!titleInput.value && this.files[0]) {
                // Remove extension and use filename as title
                const filename = this.files[0].name;
                const title = filename.substring(0, filename.lastIndexOf('.')) || filename;
                titleInput.value = title.replace(/[_-]/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            }
        });
    }
});
