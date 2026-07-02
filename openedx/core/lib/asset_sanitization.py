"""
Storage-agnostic sanitization of uploaded static assets.

This module holds the pure (bytes -> bytes) postprocessing logic shared by
every asset storage stack in the platform. It deliberately imports nothing
from xmodule, the contentstore or Learning Core, so any storage layer can
call into it without creating import cycles:

* Course assets (MongoDB/GridFS contentstore): wired in through the
  ``SanitizingContentStore`` engine in
  ``openedx.core.lib.sanitizing_contentstore``.
* Content Libraries v2 assets (Learning Core): wired in at the
  ``content_libraries`` Python API, which is the narrowest point all
  library media writes share.

Routing is based on the actual leading bytes of the file as well as the
declared content type and extension: declared metadata is client
controlled, and an SVG uploaded as "image.png" must still be sanitized.
"""

import logging
import re
from xml.etree import ElementTree

import lxml.html
from defusedxml.ElementTree import fromstring as defused_xml_fromstring
from lxml_html_clean import Cleaner

log = logging.getLogger(__name__)

SVG_MIME_TYPE = 'image/svg+xml'
SVG_NAMESPACE = 'http://www.w3.org/2000/svg'
SVG_EXTENSIONS = ('.svg',)
HTML_MIME_TYPE = 'text/html'
HTML_EXTENSIONS = ('.html', '.htm')

SNIFF_SIZE = 4096

# Browsers strip ASCII control characters and spaces when resolving a URL
# scheme, so "jav\tascript:" is executable and must be matched too.
_SCHEME_NOISE = re.compile(r'[\x00-\x20]+')

# Remove only the JavaScript vectors (script elements, on* attributes,
# javascript: URLs); every non-default False below disables a Cleaner
# behavior that would strip legitimate non-executable content.
_HTML_JS_CLEANER = Cleaner(
    scripts=True,
    javascript=True,
    comments=False,
    style=False,
    links=False,
    meta=False,
    page_structure=False,
    embedded=False,
    frames=False,
    forms=False,
    annoying_tags=False,
    safe_attrs_only=False,
)


class AssetSanitizationError(Exception):
    """Raised for an upload that cannot be parsed, and thus not sanitized."""


def sanitize_asset(file_path, data, declared_mime_type=None):
    """
    Sanitize one fully materialized asset file.

    Strips the JavaScript vectors from SVG and HTML documents, detected by
    content sniffing, declared mime type or file extension. All other data
    is returned unchanged.

    Takes bytes, returns bytes. Raises ``AssetSanitizationError`` when a
    file identified as SVG/HTML cannot be parsed.
    """
    sanitizer = pick_sanitizer(data[:SNIFF_SIZE], declared_mime_type, file_path)
    if sanitizer is None:
        return data
    sanitized = sanitizer(data)
    if sanitized != data:
        log.info('Stripped JavaScript from asset %s', file_path)
    return sanitized


def pick_sanitizer(head, declared_mime_type, name):
    """
    Return the sanitizer function for a file, or None when none applies.

    ``head`` is the leading bytes of the file (up to ``SNIFF_SIZE``);
    ``declared_mime_type`` and ``name`` are client-supplied metadata used as
    a fallback so that e.g. an unparseable file named ".svg" is still routed
    to (and rejected by) the SVG sanitizer.
    """
    sniffed = sniff_markup_type(head)
    if sniffed == 'svg' or _matches_declared_type(declared_mime_type, name, SVG_MIME_TYPE, SVG_EXTENSIONS):
        return strip_javascript_from_svg
    if sniffed == 'html' or _matches_declared_type(declared_mime_type, name, HTML_MIME_TYPE, HTML_EXTENSIONS):
        return strip_javascript_from_html
    return None


def sniff_markup_type(head):
    """
    Detect SVG or HTML documents from their leading bytes.

    Deliberately conservative: only files that start with markup (after an
    optional BOM and whitespace) are candidates, so binary formats whose
    payload happens to contain markup byte sequences are never matched.
    """
    if head.startswith(b'\xef\xbb\xbf'):  # UTF-8 BOM
        head = head[3:]
    head = head.lstrip().lower()
    if not head.startswith(b'<'):
        return None
    if head.startswith((b'<!doctype html', b'<html')) or b'<html' in head:
        return 'html'
    if b'<svg' in head or b'<!doctype svg' in head:
        return 'svg'
    return None


def strip_javascript_from_svg(svg_data):
    """
    Remove the JavaScript execution vectors from an SVG document.

    Removes ``<script>`` elements (in any namespace), ``on*`` event handler
    attributes, and ``href``/``xlink:href`` attributes with a ``javascript:``
    URL. Takes bytes, returns sanitized bytes.

    Raises ``AssetSanitizationError`` when the document cannot be parsed: a
    file we cannot inspect must not be stored as image/svg+xml.
    """
    try:
        root = defused_xml_fromstring(svg_data)
    except Exception as exc:
        raise AssetSanitizationError(f'Could not parse SVG file: {exc}') from exc

    if _local_name(root.tag) == 'script':
        raise AssetSanitizationError('SVG root element is a script element.')

    parent_of = {child: parent for parent in root.iter() for child in parent}

    for element in list(root.iter()):
        if _local_name(element.tag) == 'script':
            parent_of[element].remove(element)
            continue
        for attribute in list(element.attrib):
            name = _local_name(attribute).lower()
            if name.startswith('on') or (name == 'href' and _is_javascript_url(element.attrib[attribute])):
                del element.attrib[attribute]

    return _serialize(root)


def strip_javascript_from_html(html_data):
    """
    Remove the JavaScript execution vectors from an HTML document.

    Removes ``<script>`` elements, ``on*`` event handler attributes and
    ``javascript:`` URLs, while keeping non-executable content (styles,
    forms, iframes, comments) intact. Takes bytes, returns sanitized bytes.

    Raises ``AssetSanitizationError`` when the document cannot be parsed.
    """
    try:
        document = lxml.html.document_fromstring(html_data)
        _HTML_JS_CLEANER(document)
        doctype = document.getroottree().docinfo.doctype
        return lxml.html.tostring(document, encoding='utf-8', doctype=doctype or None)
    except Exception as exc:
        raise AssetSanitizationError(f'Could not parse HTML file: {exc}') from exc


# URL-encoding is used for all characters, including the ones HTML cares
# about (< and >): the encoded output contains no character that is itself
# encoded, which keeps this idempotent when an asset is saved again (course
# rerun, move to trashcan).
_NAME_ENCODE_MAP = str.maketrans({
    '<': '%3C',
    '>': '%3E',
    '?': '%3F',
    '&': '%26',
    '/': '%2F',
    ' ': '%20',
})


def encode_special_characters(name):
    """
    Encode the characters of an asset display name that are unsafe in URL and
    HTML contexts.
    """
    return name.translate(_NAME_ENCODE_MAP)


def _matches_declared_type(declared_mime_type, name, mime_type, extensions):
    declared = (declared_mime_type or '').split(';')[0].strip().lower()
    return declared == mime_type or (name or '').lower().endswith(extensions)


def _local_name(tag):
    """Return the tag or attribute name without its namespace qualifier."""
    if not isinstance(tag, str):  # comments and processing instructions have non-string tags
        return ''
    return tag.rpartition('}')[2]


def _is_javascript_url(value):
    return _SCHEME_NOISE.sub('', value).lower().startswith('javascript:')


def _serialize(root):
    """Serialize back to bytes, keeping SVG as the default namespace when possible."""
    try:
        return ElementTree.tostring(
            root, encoding='utf-8', xml_declaration=True, default_namespace=SVG_NAMESPACE,
        )
    except ValueError:
        # Documents mixing namespaced and unqualified names cannot use a
        # default namespace; prefixed serialization is equally valid SVG.
        return ElementTree.tostring(root, encoding='utf-8', xml_declaration=True)
