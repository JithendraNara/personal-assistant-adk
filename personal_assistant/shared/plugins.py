"""
Plugin system — dynamic loading and management of plugins.

Adapted from OpenClaw's plugins architecture (src/plugins/).
Each plugin has a plugin.json manifest + Python module with hooks.

Plugin directory structure:
    plugins/
        my_plugin/
            plugin.json     — manifest (name, version, description, hooks)
            __init__.py     — Python module with hook implementations
"""

import os
import json
import importlib
import importlib.util
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class Plugin:
    """A loaded plugin definition."""
    name: str
    version: str
    description: str
    enabled: bool = True
    hooks: dict[str, Callable] = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    source_path: str = ""


class PluginManager:
    """
    Plugin discovery, loading, and lifecycle management.

    Adapted from OpenClaw's plugin system:
      - Auto-discovers plugins from a directory
      - Loads plugin.json manifest for metadata
      - Imports Python modules for hook implementations
      - Provides hook execution (before_turn, after_turn, on_tool_call, etc.)
    """

    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = plugins_dir
        self._plugins: dict[str, Plugin] = {}

    def discover(self) -> list[Plugin]:
        """Discover all plugins from the plugins directory."""
        if not os.path.isdir(self.plugins_dir):
            logger.info(f"No plugins directory at {self.plugins_dir}")
            return []

        discovered = []
        for entry in os.listdir(self.plugins_dir):
            plugin_dir = os.path.join(self.plugins_dir, entry)
            if not os.path.isdir(plugin_dir):
                continue

            manifest_path = os.path.join(plugin_dir, "plugin.json")
            if not os.path.isfile(manifest_path):
                continue

            try:
                plugin = self._load_plugin(plugin_dir, manifest_path)
                if plugin:
                    discovered.append(plugin)
            except Exception as e:
                logger.error(f"Failed to load plugin from {plugin_dir}: {e}")

        return discovered

    def _load_plugin(self, plugin_dir: str, manifest_path: str) -> Optional[Plugin]:
        """Load a single plugin from its directory."""
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        name = manifest.get("name", os.path.basename(plugin_dir))
        plugin = Plugin(
            name=name,
            version=manifest.get("version", "0.1.0"),
            description=manifest.get("description", ""),
            enabled=manifest.get("enabled", True),
            config=manifest.get("config", {}),
            source_path=plugin_dir,
        )

        if not plugin.enabled:
            logger.info(f"Plugin '{name}' is disabled, skipping")
            return plugin

        # Load Python hooks if __init__.py exists
        init_path = os.path.join(plugin_dir, "__init__.py")
        if os.path.isfile(init_path):
            try:
                spec = importlib.util.spec_from_file_location(
                    f"plugins.{name}", init_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Register known hooks
                for hook_name in ["on_load", "on_unload", "before_turn", "after_turn",
                                  "on_tool_call", "on_error", "on_message"]:
                    if hasattr(module, hook_name):
                        plugin.hooks[hook_name] = getattr(module, hook_name)

                logger.info(f"Plugin '{name}' loaded with hooks: {list(plugin.hooks.keys())}")
            except Exception as e:
                logger.error(f"Failed to load hooks for plugin '{name}': {e}")
        else:
            logger.info(f"Plugin '{name}' loaded (no hooks, manifest only)")

        return plugin

    def load_all(self) -> None:
        """Discover and register all plugins."""
        plugins = self.discover()
        for plugin in plugins:
            self._plugins[plugin.name] = plugin
            # Execute on_load hook
            if "on_load" in plugin.hooks:
                try:
                    plugin.hooks["on_load"](plugin.config)
                except Exception as e:
                    logger.error(f"Plugin '{plugin.name}' on_load failed: {e}")

        logger.info(f"Loaded {len(self._plugins)} plugins")

    def unload_all(self) -> None:
        """Unload all plugins, calling on_unload hooks."""
        for name, plugin in self._plugins.items():
            if "on_unload" in plugin.hooks:
                try:
                    plugin.hooks["on_unload"]()
                except Exception as e:
                    logger.error(f"Plugin '{name}' on_unload failed: {e}")
        self._plugins.clear()

    async def execute_hook(self, hook_name: str, *args: Any, **kwargs: Any) -> list[Any]:
        """
        Execute a named hook across all enabled plugins.

        Returns list of results from each plugin's hook.
        """
        results = []
        for name, plugin in self._plugins.items():
            if not plugin.enabled:
                continue
            hook = plugin.hooks.get(hook_name)
            if hook:
                try:
                    import asyncio
                    if asyncio.iscoroutinefunction(hook):
                        result = await hook(*args, **kwargs)
                    else:
                        result = hook(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Plugin '{name}' hook '{hook_name}' failed: {e}")
        return results

    def list_plugins(self) -> list[dict]:
        """List all registered plugins with their status."""
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "enabled": p.enabled,
                "hooks": list(p.hooks.keys()),
            }
            for p in self._plugins.values()
        ]

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)
