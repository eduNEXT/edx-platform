0024 Plugin-Based XBlock Runtime Service Registration
####################################################

Status
******

**Proposed**


Context
*******

The XBlock specification provides a **services** mechanism that allows blocks
to request platform capabilities via ``@XBlock.needs("service_name")`` or
``@XBlock.wants("service_name")`` and retrieve them at runtime with
``self.runtime.service(self, "service_name")``.

In edx-platform, XBlock runtime services are registered in **four** separate
locations, all of which are hardcoded:

1. **LMS legacy runtime** —
   ``lms/djangoapps/courseware/block_render.py:prepare_runtime_for_user()``
   builds a dict of ~28 services and force-writes them via
   ``runtime._services.update(services)``.

2. **CMS preview** —
   ``cms/djangoapps/contentstore/views/preview.py:_prepare_runtime_for_preview()``
   builds a similar dict of ~10 services.

3. **CMS Studio view** —
   ``cms/djangoapps/contentstore/utils.py:load_services_for_studio()``
   builds a dict of ~7 services.

4. **Modern ``XBlockRuntime``** —
   ``openedx/core/djangoapps/xblock/runtime/runtime.py:XBlockRuntime.service()``
   uses a hardcoded ``if/elif`` chain for ~12 services.

There is **no plugin-friendly extension point** for external Open edX plugins
to register new XBlock services.  This forces plugins that need to expose
functionality to XBlocks to resort to monkey-patching
``xblock.runtime.Runtime.service()`` from their ``AppConfig.ready()`` method — a
pattern that, while functional, is fragile and difficult to discover.

Open edX already defines ~15 ``openedx.*`` setuptools entry-point groups (e.g.
``openedx.course_tab``, ``openedx.dynamic_partition_generator``,
``openedx.block_structure_transformer``) as the standard extensibility pattern
for plugins.  XBlock services are a natural fit for the same approach.


Decision
********

We introduce a new setuptools entry-point group called
**``openedx.xblock_service``** that allows Open edX plugins to register XBlock
runtime service factories without modifying edx-platform.

**Entry-point contract**

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Aspect
     - Specification
   * - Group name
     - ``openedx.xblock_service``
   * - Entry-point name
     - The service name that XBlocks will use (e.g. ``ai_extensions``)
   * - Callable
     - A function or class accepting ``(runtime, block)`` and returning a
       service instance, or ``None``.
   * - Error handling
     - If the factory raises an exception, the runtime logs the error and
       returns ``None``, honouring the ``@XBlock.wants`` contract.
   * - Override protection
     - Plugin services **cannot** override core services. In the modern
       ``XBlockRuntime``, core services are resolved in the ``if/elif`` chain
       before reaching the plugin fallback. In legacy runtimes, plugin
       services are only added when the service name is not already present
       in ``_services``.

**Plugin registration example**

A plugin declares its service in ``setup.cfg``:

.. code-block:: ini

    [options.entry_points]
    openedx.xblock_service =
        ai_extensions = my_plugin.xblock_services:ai_extensions_factory

The factory:

.. code-block:: python

    def ai_extensions_factory(runtime, block):
        """Build the AI Extensions service from the current runtime context."""
        user = getattr(runtime, "user", None)
        course_id = getattr(block.scope_ids.usage_id, "context_key", None)
        return AIExtensionsXBlockService(user=user, course_id=course_id)

**XBlock usage**

.. code-block:: python

    @XBlock.wants("ai_extensions")
    class MyXBlock(XBlock):

        @XBlock.json_handler
        def ask(self, data, suffix=""):
            ai = self.runtime.service(self, "ai_extensions")
            if ai is None:
                return {"error": "AI service not available"}
            return ai.call_llm(prompt="You are a tutor.", user_input=data["q"])

**Discovery module**

A new module ``openedx/core/djangoapps/xblock/runtime/plugin_services.py``
provides:

* ``_discover_service_factories()`` — scans ``openedx.xblock_service`` entry
  points at startup (result is ``lru_cache``-d for the process lifetime).
* ``get_plugin_service(service_name, runtime, block)`` — looks up a plugin
  service by name and calls the factory.  Returns ``None`` if no plugin
  provides the requested service or if the factory fails.

**Integration points**

The plugin fallback is added to all four service registration sites:

1. ``XBlockRuntime.service()`` — after the core ``if/elif`` chain, before
   ``super().service()``.
2. ``prepare_runtime_for_user()`` — after ``runtime._services.update()``,
   plugin factories are merged for names not already present.
3. ``_prepare_runtime_for_preview()`` — same pattern.
4. ``load_services_for_studio()`` — same pattern.


Consequences
************

* **Plugin authors** get a clean, documented extension point to register
  XBlock services via standard Python packaging — no monkey-patching needed.
* **Core services are protected** — plugins cannot accidentally override
  built-in services like ``user``, ``i18n``, or ``field-data``.
* **XBlocks using ``@XBlock.wants``** degrade gracefully when the plugin is
  absent, maintaining portability to the XBlock SDK test runner.
* **Performance impact is negligible** — entry-point scanning happens once
  per process (cached via ``lru_cache``), and the per-request dict lookup
  in ``get_plugin_service`` is O(1).
* **Existing plugins** that use the monkey-patch approach can migrate at
  their own pace.  The monkey-patch and entry-point approaches can coexist
  safely during migration.
* Service factories receive ``(runtime, block)`` which provides access to
  user, course context, and block location — sufficient for most service
  implementations.


Rejected Alternatives
*********************

**Django signals as a registry**

Signals lack a clean synchronous return-value mechanism and would produce
a poor developer experience for service registration.

**Django setting (``XBLOCK_SERVICES``)**

A settings-based dict would require operators to manually configure each
service.  Entry points are discovered automatically from installed packages,
which aligns with the existing Open edX plugin model.

**``XBLOCK_MIXINS`` setting**

``XBLOCK_MIXINS`` mixes classes into XBlock *block classes*, not into
runtimes.  It cannot be used to register runtime services.

**openedx_filters / openedx_events**

These frameworks are designed for request-level hooks, not for one-time
service registration.  Using a filter to inject services on every
``service()`` call would add unnecessary overhead.


References
**********

* XBlock services documentation — https://docs.openedx.org/projects/xblock/en/latest/
* Open edX plugin entry points — ``setup.py`` in edx-platform
* ``openedx-ai-extensions`` ADR 0004 (monkey-patch approach) —
  https://github.com/openedx/openedx-ai-extensions/blob/main/docs/decisions/0004-xblock-ai-service.rst
* ``plugin_services.py`` — ``openedx/core/djangoapps/xblock/runtime/plugin_services.py``
