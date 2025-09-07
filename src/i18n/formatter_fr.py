#!/usr/bin/env python3
"""
File: formatter_fr.py
Author: Bastian Cerf
Date: 06/09/2025
Description:
    Internationalization (i18n) service.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Internal libraries
from i18n.translations import LanguageFormatter
import datetime as dt


class FrenchFormatter(LanguageFormatter):
    """
    Formatter implementation for the french language.
    """

    def greeting(self, now: dt.datetime | dt.time, farewell: bool = False) -> str:
        if farewell:
            return "Au revoir"
        if now.hour < 17:
            return "Bonjour"
        else:
            return "Bonsoir"
