#!/usr/bin/env python3
"""
File: translations.py
Author: Bastian Cerf
Date: 06/09/2025
Description:
    Internationalization (i18n) service.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
from os.path import join
from pathlib import Path
from typing import Optional
from gettext import GNUTranslations
import polib

# Internal libraries
from local_config import LocalConfig
from common.singleton_register import SingletonRegister

logger = logging.getLogger(__name__)

LOCALES_DIRECTORY = join("assets", "locales")


class LanguageService(SingletonRegister):
    """
    The language service is a singleton providing access to the loaded
    translation units. They are compiled and loaded at application
    startup and accessed using the `get_translator()` method. A
    `translation()` method is also provided for convenience.
    """

    def _setup(self):
        """
        Setup the language service. Compile and load all available
        language files.
        """
        self._translators: dict[str, GNUTranslations] = {}
        self._compile_po_files()
        self._load_languages()

        def_lang = LocalConfig().section("general")["language"]
        try:
            self._def_lang = self._translators[def_lang]
        except KeyError:
            raise FileNotFoundError(
                f"No translation file found for default language '{def_lang}'."
            )

    def _compile_po_files(self):
        """
        Compile all .po files into .mo files. The .po files must be
        located under `locales/*language*/file.po`.
        """
        for po_file in Path(LOCALES_DIRECTORY).rglob("*.po"):
            mo_file = po_file.with_suffix(".mo")
            if (
                not mo_file.exists()
                or mo_file.stat().st_mtime < po_file.stat().st_mtime
            ):
                po = polib.pofile(str(po_file))
                po.save_as_mofile(str(mo_file))
                logger.debug(f"Compiled '{mo_file}' from '{po_file}'.")
            else:
                logger.debug(f"Skipped already compiled '{mo_file}'.")

    def _load_languages(self):
        """
        Load translators for all available languages.
        """
        for mo_file in Path(LOCALES_DIRECTORY).rglob("*.mo"):
            # Ensure mo file is under locales/lang/file.mo
            if not mo_file.parent.parent.samefile(Path(LOCALES_DIRECTORY)):
                raise RuntimeError(
                    f"Invalid translation file location: '{mo_file}'. "
                    f"Expected under '{Path(LOCALES_DIRECTORY) / "*language*"}'."
                )

            lang = mo_file.parent.name
            with open(mo_file, "rb") as fb:
                self._translators[lang] = GNUTranslations(fb)
            logger.info(f"Created translator for language '{lang}'.")

    def get_translator(self, lang: Optional[str] = None) -> GNUTranslations:
        """
        Get a translation unit. Fallback to default if not provided or
        not existing.

        Returns:
            GNUTranslations: Translation unit.
        """
        if lang:
            return self._translators.get(lang, self._def_lang)
        return self._def_lang

    def translation(self, msgid: str, lang: Optional[str] = None) -> str:
        """
        Get a translation from message ID for a given language.

        Returns:
            str: Translation for the message ID.
        """
        return self.get_translation(lang).gettext(msgid)
