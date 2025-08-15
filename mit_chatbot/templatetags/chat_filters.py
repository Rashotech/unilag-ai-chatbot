from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()


@register.filter
def format_assistant_message(content):
    """
    Format assistant message content and mark as safe HTML
    """
    if not content:
        return content

    formatted = str(content)

    # Convert **bold** text
    formatted = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', formatted)

    # Convert headers
    formatted = re.sub(
        r'^### (.+)$',
        r'<h3 style="font-size:1.1em; font-weight:bold; margin:15px 0 8px 0; color:#1f2937;">\1</h3>',
        formatted,
        flags=re.MULTILINE
    )
    formatted = re.sub(
        r'^## (.+)$',
        r'<h2 style="font-size:1.2em; font-weight:bold; margin:18px 0 10px 0; color:#1f2937;">\1</h2>',
        formatted,
        flags=re.MULTILINE
    )

    # Convert bullet points
    formatted = re.sub(r'^\s*\*\s*(.+)$', r'<li style="margin-bottom:8px;">\1</li>', formatted, flags=re.MULTILINE)

    # Wrap lists with custom function
    def wrap_lists(match):
        return f'<ul style="margin:10px 0; padding-left:20px;">{match.group(0)}</ul>'

    formatted = re.sub(r'(<li[^>]*>.*?</li>\s*)+', wrap_lists, formatted, flags=re.DOTALL)

    # Handle source citations
    formatted = re.sub(
        r'\*$ Source:([^)]+) $ \*',
        r'<div style="font-size:0.85em; color:#666; font-style:italic; margin-top:10px; padding:8px; background:#f9f9f9; border-left:3px solid #ddd;">Source: \1</div>',
        formatted
    )

    # Convert to paragraphs
    sections = re.split(r'\n\s*\n', formatted)
    formatted_sections = []

    for section in sections:
        section = section.strip()
        if section and not re.match(r'^<(h[1-6]|ul|div|li)', section, re.IGNORECASE):
            formatted_sections.append(f'<p style="margin-bottom:12px; line-height:1.5;">{section}</p>')
        elif section:
            formatted_sections.append(section)

    formatted = '\n\n'.join(formatted_sections)

    # Handle remaining line breaks
    formatted = re.sub(r'\n(?![^<]*>)', '<br>', formatted)

    # Mark as safe HTML to prevent escaping
    return mark_safe(formatted.strip())