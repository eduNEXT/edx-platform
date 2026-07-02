"""
Tests for the sanitizing contentstore engine and its postprocessing steps.
"""

import pytest

from opaque_keys.edx.keys import CourseKey
from xmodule.contentstore.content import StaticContent

from openedx.core.lib.sanitizing_contentstore import (
    AssetSanitizationError,
    SanitizingContentStore,
    encode_special_characters,
    process_uploaded_content,
    strip_javascript_from_html,
    strip_javascript_from_svg,
)

MALICIOUS_SVG = b"""<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     onload="alert('onload')">
  <script>alert('script element')</script>
  <script xmlns="http://www.w3.org/1999/xhtml">alert('html script')</script>
  <a href="javascript:alert('href')"><text>click</text></a>
  <a xlink:href="jav&#9;ascript:alert('obfuscated')"><text>click too</text></a>
  <circle cx="50" cy="50" r="40" onclick="alert('onclick')" fill="green"/>
</svg>
"""

CLEAN_SVG = b"""<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="40" fill="green"/>
  <a href="https://example.com"><text>a normal link</text></a>
</svg>
"""

MALICIOUS_HTML = b"""<!DOCTYPE html>
<html>
<head>
  <title>Course page</title>
  <style>body { color: green; }</style>
  <script src="https://evil.example.com/payload.js"></script>
</head>
<body onload="alert('onload')">
  <h1>Welcome</h1>
  <a href="javascript:alert('href')">click</a>
  <a href="https://example.com">a normal link</a>
  <img src="cat.png" onerror="alert('onerror')">
  <iframe src="https://example.com/embed"></iframe>
  <script>alert('inline')</script>
</body>
</html>
"""


def _make_content(name, mime_type, data):
    course_key = CourseKey.from_string('course-v1:TestX+SAN+2026')
    location = StaticContent.compute_location(course_key, name)
    return StaticContent(location, name, mime_type, data)


class TestStripJavascriptFromSvg:
    """Tests for the pure bytes -> bytes SVG sanitizer."""

    def test_removes_all_javascript_vectors(self):
        result = strip_javascript_from_svg(MALICIOUS_SVG).decode('utf-8')

        assert 'script' not in result.lower()
        assert 'alert' not in result
        assert 'onload' not in result
        assert 'onclick' not in result
        assert 'javascript:' not in result.lower()

    def test_keeps_drawing_content(self):
        result = strip_javascript_from_svg(MALICIOUS_SVG).decode('utf-8')

        assert 'circle' in result
        assert 'fill="green"' in result

    def test_clean_svg_keeps_safe_attributes_and_links(self):
        result = strip_javascript_from_svg(CLEAN_SVG).decode('utf-8')

        assert 'viewBox="0 0 100 100"' in result
        assert 'https://example.com' in result

    def test_unparseable_file_is_rejected(self):
        with pytest.raises(AssetSanitizationError):
            strip_javascript_from_svg(b'<svg onload="alert(1)"')

    def test_script_as_root_element_is_rejected(self):
        with pytest.raises(AssetSanitizationError):
            strip_javascript_from_svg(b'<script>alert(1)</script>')


class TestStripJavascriptFromHtml:
    """Tests for the pure bytes -> bytes HTML sanitizer."""

    def test_removes_all_javascript_vectors(self):
        result = strip_javascript_from_html(MALICIOUS_HTML).decode('utf-8')

        assert 'script' not in result.lower()
        assert 'alert' not in result
        assert 'onload' not in result
        assert 'onerror' not in result
        assert 'javascript:' not in result.lower()

    def test_keeps_non_executable_content(self):
        result = strip_javascript_from_html(MALICIOUS_HTML).decode('utf-8')

        assert '<!DOCTYPE html>' in result
        assert '<title>Course page</title>' in result
        assert 'color: green' in result
        assert '<h1>Welcome</h1>' in result
        assert 'https://example.com/embed' in result
        assert 'https://example.com">a normal link' in result

    def test_empty_file_is_rejected(self):
        with pytest.raises(AssetSanitizationError):
            strip_javascript_from_html(b'')


class TestEncodeSpecialCharacters:
    """Tests for the display name encoding step."""

    def test_encodes_all_special_characters(self):
        assert encode_special_characters('a b<c>d?e&f/g.html') == 'a%20b%3Cc%3Ed%3Fe%26f%2Fg.html'

    def test_is_idempotent(self):
        once = encode_special_characters('my file <1> & co.svg')

        assert encode_special_characters(once) == once

    def test_plain_name_is_unchanged(self):
        assert encode_special_characters('logo-v2.1_final.svg') == 'logo-v2.1_final.svg'


class TestProcessUploadedContent:
    """Tests for the content-type routing step."""

    def test_svg_by_mime_type_is_sanitized(self):
        content = process_uploaded_content(_make_content('logo.svg', 'image/svg+xml', MALICIOUS_SVG))

        assert b'alert' not in content.data
        assert content.length == len(content.data)

    def test_svg_by_extension_is_sanitized(self):
        content = process_uploaded_content(_make_content('logo.svg', None, MALICIOUS_SVG))

        assert b'alert' not in content.data

    def test_html_is_sanitized(self):
        content = process_uploaded_content(_make_content('page.html', 'text/html', MALICIOUS_HTML))

        assert b'alert' not in content.data
        assert content.length == len(content.data)

    def test_chunked_upload_data_is_supported(self):
        chunks = iter([MALICIOUS_SVG[:100], MALICIOUS_SVG[100:]])
        content = process_uploaded_content(_make_content('logo.svg', 'image/svg+xml', chunks))

        assert isinstance(content.data, bytes)
        assert b'alert' not in content.data

    def test_non_svg_content_is_untouched(self):
        pdf_bytes = b'%PDF-1.4 fake pdf with <script>alert(1)</script> inside'
        content = process_uploaded_content(_make_content('doc.pdf', 'application/pdf', pdf_bytes))

        assert content.data is pdf_bytes

    def test_svg_disguised_as_png_is_sanitized(self):
        content = process_uploaded_content(_make_content('uncool.png', 'image/png', MALICIOUS_SVG))

        assert b'alert' not in content.data

    def test_html_disguised_as_png_is_sanitized(self):
        content = process_uploaded_content(_make_content('uncool.png', 'image/png', MALICIOUS_HTML))

        assert b'alert' not in content.data

    def test_chunked_svg_disguised_as_png_is_sanitized(self):
        chunks = iter([MALICIOUS_SVG[:100], MALICIOUS_SVG[100:]])
        content = process_uploaded_content(_make_content('uncool.png', 'image/png', chunks))

        assert b'alert' not in content.data

    def test_real_binary_with_embedded_markup_bytes_is_untouched(self):
        png_bytes = b'\x89PNG\r\n\x1a\n' + b'binary junk <svg onload="alert(1)"> more junk'
        content = process_uploaded_content(_make_content('real.png', 'image/png', png_bytes))

        assert content.data is png_bytes

    def test_chunked_binary_still_streams(self):
        chunks = iter([b'\x89PNG\r\n\x1a\n' + b'x' * 5000, b'y' * 5000])
        content = process_uploaded_content(_make_content('big.png', 'image/png', chunks))

        assert not isinstance(content.data, bytes)  # still a lazy iterable
        assert b''.join(content.data) == b'\x89PNG\r\n\x1a\n' + b'x' * 5000 + b'y' * 5000

    def test_display_name_is_encoded_for_any_file_type(self):
        content = process_uploaded_content(_make_content('my doc & notes.pdf', 'application/pdf', b'%PDF-1.4'))

        assert content.name == 'my%20doc%20%26%20notes.pdf'


def test_sanitizing_contentstore_subclasses_mongo_engine():
    from xmodule.contentstore.mongo import MongoContentStore

    assert issubclass(SanitizingContentStore, MongoContentStore)
    assert 'save' in SanitizingContentStore.__dict__
