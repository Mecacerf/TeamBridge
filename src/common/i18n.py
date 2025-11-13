#!/usr/bin/env python3
"""Internationalization helpers."""

from __future__ import annotations

# Standard libraries
import json
import logging
from os.path import join
from typing import Any, Mapping, Optional

# Internal libraries
from .singleton_register import SingletonRegister
from common.config_parser import ConfigError
from local_config import LocalConfig

logger = logging.getLogger(__name__)

_DEFAULT_LANGUAGE = "en"
_I18N_DIR = join("assets", "i18n")


def _normalize_language(value: Optional[str]) -> str:
    if not value:
        return _DEFAULT_LANGUAGE

    normalized = value.replace("-", "_")
    parts = normalized.split("_")
    if parts and parts[0]:
        return parts[0].lower()
    return _DEFAULT_LANGUAGE


class Translator(SingletonRegister):
    """Load translation catalogs and provide lookup helpers."""

    def _setup(
        self,
        language: Optional[str] = None,
        translations_path: str = _I18N_DIR,
        fallback_language: str = _DEFAULT_LANGUAGE,
    ) -> None:
        self._translations_path = translations_path
        self._fallback_language = fallback_language

        if language is None:
            try:
                config = LocalConfig()
                language = _normalize_language(config.section("general")["locale"])
            except (KeyError, ConfigError):
                language = _DEFAULT_LANGUAGE

        self._language = language or _DEFAULT_LANGUAGE
        self._catalog = self._load_catalog(self._language)

        if not self._catalog and self._language != fallback_language:
            logger.warning(
                "No translations found for language '%s'. Falling back to '%s'.",
                self._language,
                fallback_language,
            )
            self._language = fallback_language
            self._catalog = self._load_catalog(self._language)

        self._fallback_catalog: Mapping[str, str]
        if self._language == fallback_language:
            self._fallback_catalog = {}
        else:
            self._fallback_catalog = self._load_catalog(fallback_language)

    def _load_catalog(self, language: str) -> Mapping[str, str]:
        path = join(self._translations_path, f"{language}.json")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            logger.warning("Translation file for language '%s' not found at '%s'.", language, path)
            return {}
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse translation file '%s': %s", path, exc)
            return {}

        if not isinstance(data, dict):
            logger.error("Invalid translation catalog '%s': expected a JSON object.", path)
            return {}

        return {str(key): str(value) for key, value in data.items()}

    @property
    def language(self) -> str:
        return self._language

    def translate(self, key: str, **kwargs: Any) -> str:
        template = self._catalog.get(key)
        if template is None:
            template = self._fallback_catalog.get(key)
            if template is None:
                logger.warning("Missing translation key '%s' for language '%s'.", key, self._language)
                return key

        try:
            return template.format(**kwargs)
        except KeyError as exc:
            logger.error("Missing placeholder %s for translation key '%s'.", exc, key)
            return template

    def plural_suffix(self, count: int) -> str:
        return "" if count == 1 else self.translate("plural.s")


def translate(key: str, **kwargs: Any) -> str:
    """Translate a key using the configured translator."""

    return Translator().translate(key, **kwargs)


def plural_suffix(count: int) -> str:
    """Return the plural suffix for the active language."""

    return Translator().plural_suffix(count)
