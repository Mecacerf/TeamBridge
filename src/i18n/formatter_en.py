#!/usr/bin/env python3
"""
File: formatter_en.py
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


class EnglishFormatter(LanguageFormatter):
    """
    Formatter implementation for the english language.
    """

    def greeting(self, now: dt.datetime | dt.time, farewell: bool = False) -> str:
        if farewell:
            return "Goodbye"
        if now.hour < 12:
            return "Good morning"
        elif now.hour < 17:
            return "Good afternoon"
        elif now.hour < 21:
            return "Good evening"
        else:
            return "Good night"
