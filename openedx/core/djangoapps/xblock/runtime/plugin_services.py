"""
Plugin-based XBlock service discovery via the ``openedx.xblock_service`` entry point.

This module allows Open edX plugins to register new XBlock runtime services
without modifying edx-platform core.  A plugin declares its service factory
in its ``setup.cfg`` (or ``setup.py``) under the ``openedx.xblock_service``
entry-point group::

    [options.entry_points]
    openedx.xblock_service =
        my_service = my_plugin.xblock_services:MyServiceFactory

Each entry point **name** becomes the service name that XBlocks request via
``self.runtime.service(self, "my_service")``.

The entry point **value** must be a callable (class or function) that accepts
``(runtime, block)`` and returns a service instance, or ``None`` if the
service cannot be provided in the current context.

Plugin-provided services **cannot** override core services that are already
hardcoded in ``XBlockRuntime.service()``, ``prepare_runtime_for_user()``, or
their CMS equivalents.  This prevents plugins from accidentally breaking
platform functionality.
"""

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "openedx.xblock_service"


@lru_cache(maxsize=1)
def _discover_service_factories():
    """
    Scan installed packages for ``openedx.xblock_service`` entry points.

    Returns:
        dict[str, callable]: Mapping of service name -> factory callable.
            Each factory must accept ``(runtime, block)`` and return a
            service instance or ``None``.

    The result is cached for the lifetime of the process because entry
    points do not change at runtime.
    """
    from importlib.metadata import entry_points  # pylint: disable=import-outside-toplevel

    factories = {}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            factory = ep.load()
            factories[ep.name] = factory
            logger.info(
                "Registered plugin XBlock service %r from %s",
                ep.name,
                ep.value,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception(
                "Failed to load XBlock service entry point %r (%s). "
                "The service will not be available to XBlocks.",
                ep.name,
                ep.value,
            )
    return factories


def get_plugin_service(service_name, runtime, block):
    """
    Look up a plugin-provided XBlock service by *service_name*.

    Args:
        service_name (str): The service name requested by the XBlock.
        runtime: The current XBlock runtime instance.
        block: The XBlock instance requesting the service.

    Returns:
        The service instance returned by the plugin factory, or ``None``
        if no plugin provides a service with this name or if the factory
        raises an exception.
    """
    factories = _discover_service_factories()
    factory = factories.get(service_name)
    if factory is None:
        return None
    try:
        return factory(runtime, block)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Plugin XBlock service %r raised an error during instantiation "
            "for block %r. Returning None.",
            service_name,
            getattr(block, "scope_ids", repr(block)),
        )
        return None
