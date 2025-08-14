#!/usr/bin/env python3
"""
File: local_config.py
Author: Bastian Cerf
Date: 15/08/2025
Description:
    Read and parse a the local configuration file.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
from os.path import join
from types import MappingProxyType
from typing import Any

# Internal libraries
from common.config_parser import ConfigParser
from common.singleton_register import SingletonRegister

SCHEMA_FILE_PATH = join("assets", "config", "local_config_schema.json")
CONFIG_FILE_PATH = join("local_config.ini")


class LocalConfig(SingletonRegister):
    """ """

    def _setup(self):
        """ """
        config = ConfigParser(SCHEMA_FILE_PATH, CONFIG_FILE_PATH)
        self._view = config.view()

    def section(self, section: str) -> MappingProxyType[str, Any]:
        return self._view[section]
