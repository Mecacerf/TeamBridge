#!/usr/bin/env python3
"""
File: view_theme.py
Author: Bastian Cerf
Date: 26/04/2025
Description: 
    Define base properties for a view theme.    

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

from dataclasses import dataclass

from kivy.graphics import Color
from kivy.utils import get_color_from_hex

@dataclass
class ViewTheme:
    """
    Define the view theme properties.
    """
    # Background color (main screen)
    bg_color: Color

    # Surface color (cards, panels, popups)
    surface_color: Color

    # Primary color (main brand color for buttons, highlights)
    primary_color: Color

    # Secondary color (accents, less important highlights)
    secondary_color: Color

    # Text color for primary elements (titles)
    text_primary_color: Color

    # Text color for secondary elements (subtitles, helper texts)
    text_secondary_color: Color

    # Color for borders, separators, lines
    border_color: Color

    # Error color (for warnings, invalid input, etc.)
    error_color: Color

    # Success color (for validated actions, success messages)
    success_color: Color

    # Disabled color (for disabled buttons/text)
    disabled_color: Color

    # Hint text color (placeholder text in inputs)
    hint_color: Color

# Light theme
LIGHT_THEME = ViewTheme(
    bg_color=get_color_from_hex("FFFFFF"),        
    surface_color=get_color_from_hex("D9D9D9"),     
    primary_color=get_color_from_hex("1C6EAC"),     
    secondary_color=get_color_from_hex("B9D2E5"),  
    text_primary_color=get_color_from_hex("1C6EAC"),
    text_secondary_color=get_color_from_hex("000000"), 
    border_color=get_color_from_hex("4F4F4F"),      
    error_color=get_color_from_hex("ED1C24"),               
    success_color=get_color_from_hex("1CAC3B"),            
    disabled_color=(0.55, 0.55, 0.55, 1),       
    hint_color=(0.5, 0.5, 0.5, 1),           
)

# Dark theme
DARK_THEME = ViewTheme(
    bg_color = get_color_from_hex("1F1F1F"),           
    surface_color=get_color_from_hex("3F3F3F"),      
    primary_color=get_color_from_hex("238BD9"),      
    secondary_color=get_color_from_hex("B9D2E5"),   
    text_primary_color=get_color_from_hex("238BD9"), 
    text_secondary_color=get_color_from_hex("B0BEC5"), 
    border_color=get_color_from_hex("2C2C2C"),
    error_color=(0.9, 0.3, 0.3, 1),        
    success_color=(0.3, 0.9, 0.3, 1),
    disabled_color=(0.4, 0.4, 0.4, 1),
    hint_color=(0.5, 0.5, 0.5, 1),               
)
