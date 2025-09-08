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
from typing import Optional


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
        
    def format_td_balance(self, td: Optional[dt.timedelta]) -> str:
        if td is None:
            return "indisponible"

        total_minutes = int(td.total_seconds() // 60)
        sign = "-" if total_minutes < 0 else ""
        abs_minutes = abs(total_minutes)
        hours, minutes = divmod(abs_minutes, 60)

        if hours == 0:
            return f"{sign}{minutes} minute{"s" if minutes > 1 else ""}"
        elif minutes == 0:
            return f"{sign}{hours}h"
        return f"{sign}{hours}h{minutes:02}"

    def format_date(self, date: Optional[dt.date]) -> str:
        if date:
            return dt.date.strftime(date, "%d.%m.%Y")
        return "Date inconnue"
    