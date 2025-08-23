#!/usr/bin/env python3
"""
File: local_config.py
Author: Bastian Cerf
Date: 15/08/2025
Description:
    Read, parse and validate the local configuration file
    `local_config.ini` against its schema under
    `assets/config/local_config_schema.json`.

    The `LocalConfig` class is a thread-safe singleton loaded at
    startup that can be accessed from any place of the application.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
from os.path import join
from types import MappingProxyType
from typing import Any, Optional

# Internal libraries
from common.config_parser import ConfigParser
from common.singleton_register import SingletonRegister

logger = logging.getLogger(__name__)

SCHEMA_FILE_PATH = join("assets", "config", "local_config_schema.json")
CONFIG_FILE_PATH = join("local_config.ini")


class LocalConfig(SingletonRegister):
    """
    Thread-safe singleton holding the application's configuration data.
    Available from any place of the program. The first constructor call
    creates and initializes it, while next calls just return the only
    instance.
    """

    def _setup(self, path: Optional[str] = None):
        """
        Called by `SingletonRegister` once at setup.
        Create internal `ConfigParser` object and get a read-only view
        on its data.
        """
        self._config_path = path
        if not self._config_path:
            self._config_path = CONFIG_FILE_PATH

        self._config = ConfigParser(
            SCHEMA_FILE_PATH, self._config_path, gen_default=True
        )
        self._view = self._config.get_view()

    def section(self, section: str) -> MappingProxyType[str, Any]:
        """
        Returns:
            MappingProxyType: A read-only view on a data section.
        """
        return self._view[section]

    def persist(self, section: str, key: str, value: Any):
        """
        Persist a value in the local configuration.
        """
        self._config.set_value(section, key, value)

    def show_config(self):
        """
        Log the local configuration in use, section by section.
        """
        logger.info(f"Using local configuration '{self._config_path}'.")
        for section, values in self._view.items():
            logger.info(f"Section [{section}] = {values}")
