"""
A drop-in replacement for the default contentstore engine that post-processes
course assets on upload, before they reach storage.

To activate, point the contentstore engine at this class (in both CMS and LMS,
since they share the ``CONTENTSTORE`` setting):

    CONTENTSTORE['ENGINE'] = 'openedx.core.lib.sanitizing_contentstore.SanitizingContentStore'

The implementation is deliberately split in two steps:

1. ``SanitizingContentStore.save`` -- the storage engine subclass. Every asset
   write funnels through ``ContentStore.save``, so overriding it here is the
   one place that guarantees no course asset is stored unprocessed. It knows
   nothing about file types; it only up-calls the processing step.
2. ``process_uploaded_content`` -- the processing step. It encodes unsafe
   characters in the asset's display name and routes the file body through
   the storage-agnostic sanitizers in ``openedx.core.lib.asset_sanitization``
   (shared with the Content Libraries v2 storage stack).
"""

import itertools
import logging

from xmodule.contentstore.mongo import MongoContentStore

# Some names are re-imported for backwards compatibility with earlier
# versions of this module, where the sanitizers lived here directly.
from openedx.core.lib.asset_sanitization import (  # pylint: disable=unused-import
    SNIFF_SIZE,
    AssetSanitizationError,
    encode_special_characters,
    pick_sanitizer,
    strip_javascript_from_html,
    strip_javascript_from_svg,
)

log = logging.getLogger(__name__)


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

    sanitizer = pick_sanitizer(_head_of(content), content.content_type, content.name)
    if sanitizer is None:
        return content

    data = _as_bytes(content.data)
    sanitized = sanitizer(data)
    if sanitized != data:
        log.info('Stripped JavaScript from asset %s', content.location)
    # StaticContent.data is a read-only property, so write the backing attribute.
    content._data = sanitized  # pylint: disable=protected-access
    content.length = len(sanitized)
    return content


def _head_of(content):
    """
    Return the leading bytes of the asset without losing streamed data.

    When the data is a chunk iterator (large uploads), the consumed chunks
    are chained back in front of the remaining ones so the content can still
    be streamed to storage unchanged.
    """
    data = content.data
    if isinstance(data, bytes):
        return data[:SNIFF_SIZE]
    if isinstance(data, str):
        return data.encode('utf-8')[:SNIFF_SIZE]

    iterator = iter(data)
    head_chunks = []
    head_size = 0
    for chunk in iterator:
        chunk = chunk if isinstance(chunk, bytes) else chunk.encode('utf-8')
        head_chunks.append(chunk)
        head_size += len(chunk)
        if head_size >= SNIFF_SIZE:
            break
    content._data = itertools.chain(head_chunks, iterator)  # pylint: disable=protected-access
    return b''.join(head_chunks)[:SNIFF_SIZE]


def _as_bytes(data):
    """Materialize StaticContent data, which may be bytes, str or an iterable of chunks."""
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode('utf-8')
    return b''.join(chunk if isinstance(chunk, bytes) else chunk.encode('utf-8') for chunk in data)
