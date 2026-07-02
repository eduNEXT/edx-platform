"""
A drop-in replacement for the default contentstore engine that post-processes
course assets on upload, before they reach storage.

To activate, point the contentstore engine at this class (in both CMS and LMS,
since they share the ``CONTENTSTORE`` setting):

    CONTENTSTORE['ENGINE'] = 'openedx.core.lib.sanitizing_contentstore.SanitizingContentStore'

The implementation is deliberately split in two steps:

1. ``SanitizingContentStore.save`` -- the storage engine subclass. Every asset
   write funnels through ``ContentStore.save``, so overriding it here is the
   one place that guarantees no asset is stored unprocessed. It knows nothing
   about file types; it only up-calls the processing step.
2. ``process_uploaded_content`` and the transformation functions -- the
   processing step. It encodes unsafe characters in every asset's display
   name, and strips the JavaScript vectors from SVG and HTML file bodies.
"""

import itertools
import logging
import re
from xml.etree import ElementTree

import lxml.html
from defusedxml.ElementTree import fromstring as defused_xml_fromstring
from lxml_html_clean import Cleaner

from xmodule.contentstore.mongo import MongoContentStore

log = logging.getLogger(__name__)

SVG_MIME_TYPE = 'image/svg+xml'
SVG_NAMESPACE = 'http://www.w3.org/2000/svg'
HTML_MIME_TYPE = 'text/html'
HTML_EXTENSIONS = ('.html', '.htm')

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


class SanitizingContentStore(MongoContentStore):
    """
    Contentstore engine that post-processes assets before storing them.

    Step one of the two-step design: this class only provides the choke
    point; all type detection and content transformation lives in
    ``process_uploaded_content``.
    """

    def save(self, content):
        return super().save(process_uploaded_content(content))


def process_uploaded_content(content):
    """
    Route an asset to the postprocessors that apply to its content type.

    Takes and returns a ``StaticContent`` instance, modified in place when a
    postprocessor applies. Every asset gets its display name encoded;
    SVG and HTML file bodies additionally get their JavaScript stripped.

    Routing is based on the actual leading bytes of the file as well as the
    declared content type and extension: declared metadata is client
    controlled, and an SVG uploaded as "image.png" must still be sanitized.
    """
    if content.name:
        content.name = encode_special_characters(content.name)

    sniffed = _sniff_markup_type(_head_of(content))
    if sniffed == 'svg' or _is_svg(content):
        sanitizer = strip_javascript_from_svg
    elif sniffed == 'html' or _is_html(content):
        sanitizer = strip_javascript_from_html
    else:
        return content

    data = _as_bytes(content.data)
    sanitized = sanitizer(data)
    if sanitized != data:
        log.info('Stripped JavaScript from asset %s', content.location)
    # StaticContent.data is a read-only property, so write the backing attribute.
    content._data = sanitized  # pylint: disable=protected-access
    content.length = len(sanitized)
    return content


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


def strip_javascript_from_svg(svg_data):
    """
    Step two: remove the JavaScript execution vectors from an SVG document.

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


_SNIFF_SIZE = 4096


def _head_of(content):
    """
    Return the leading bytes of the asset without losing streamed data.

    When the data is a chunk iterator (large uploads), the consumed chunks
    are chained back in front of the remaining ones so the content can still
    be streamed to storage unchanged.
    """
    data = content.data
    if isinstance(data, bytes):
        return data[:_SNIFF_SIZE]
    if isinstance(data, str):
        return data.encode('utf-8')[:_SNIFF_SIZE]

    iterator = iter(data)
    head_chunks = []
    head_size = 0
    for chunk in iterator:
        chunk = chunk if isinstance(chunk, bytes) else chunk.encode('utf-8')
        head_chunks.append(chunk)
        head_size += len(chunk)
        if head_size >= _SNIFF_SIZE:
            break
    content._data = itertools.chain(head_chunks, iterator)  # pylint: disable=protected-access
    return b''.join(head_chunks)[:_SNIFF_SIZE]


def _sniff_markup_type(head):
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


def _is_svg(content):
    return _matches_type(content, SVG_MIME_TYPE, ('.svg',))


def _is_html(content):
    return _matches_type(content, HTML_MIME_TYPE, HTML_EXTENSIONS)


def _matches_type(content, mime_type, extensions):
    content_mime_type = (content.content_type or '').split(';')[0].strip().lower()
    return content_mime_type == mime_type or (content.name or '').lower().endswith(extensions)


def _as_bytes(data):
    """Materialize StaticContent data, which may be bytes, str or an iterable of chunks."""
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode('utf-8')
    return b''.join(chunk if isinstance(chunk, bytes) else chunk.encode('utf-8') for chunk in data)


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
