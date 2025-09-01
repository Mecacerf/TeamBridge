#!/usr/bin/env python3
"""
File: config_parser_test.py
Author: Bastian Cerf
Date: 18/08/2025
Description:
    Unit test the configuration parser module.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import pytest
from pytest import approx
import io
import textwrap
from pathlib import Path
import logging

# Internal libraries
from .test_constants import TEST_ASSETS_DST_FOLDER
from common.config_parser import ConfigParser, ConfigError, _SchemaEntry, _str_to_bool

logger = logging.getLogger(__name__)

########################################################################
#                              Test data                               #
########################################################################

TEST_SCHEMA = """
{
    "section1": {
        "number": {
            "type": "int", 
            "required": true,
            "default": 8
        },
        "flag": {
            "type": "bool",
            "default": false,
            "comment": "Simple flag"
        }
    },
    "section2": {
        "text": {
            "type": "str",
            "default": "This is a default text"
        },
        "floating": {
            "type": "float",
            "default": 3.14,
            "comment": "This is PI",
            "min": 2.1
        }
    }
}
"""

TEST_CONFIG = textwrap.dedent(
    """\
        [section1]
        number = 8
        ; Simple flag
        flag = false

        [section2]
        text = This is a default text
        ; This is PI
        floating = 3.14
        
    """
)

########################################################################
#                           Schema entry test                          #
########################################################################

### Parsing test


def test_str_to_bool():
    """
    Check the output of the string to bool converting function.
    """
    assert _str_to_bool("true") == True
    assert _str_to_bool("false") == False
    assert _str_to_bool("On") == True
    assert _str_to_bool("ofF") == False
    assert _str_to_bool("1") == True
    assert _str_to_bool("0") == False
    assert _str_to_bool("yEs") == True
    assert _str_to_bool("no") == False

    with pytest.raises(ValueError):
        _str_to_bool("not a bool")


def test_missing_type_raises():
    """
    The `type` field is abolutely required in the schema entry.
    """
    with pytest.raises(ConfigError):
        _SchemaEntry("mykey", {})


def test_unknown_type_raises():
    """
    The `type` field must be of `int`, `float`, `str` or `bool`.
    """
    with pytest.raises(ConfigError):
        _SchemaEntry("mykey", {"type": "weird"})


def test_extra_field_raises():
    """
    No extra field allowed, it might be a typo the developer didn't see.
    """
    with pytest.raises(ConfigError):
        _SchemaEntry("mykey", {"type": "int", "foo": 123})


def test_wrong_field_type_raises():
    """
    An error is raised if a field doesn't hold the expected value type.
    """
    with pytest.raises(ConfigError):
        _SchemaEntry("mykey", {"type": "int", "max": "123"})


def test_properties():
    """
    Check properties return the given values.
    """
    DEFAULT = 3.14
    COMMENT = "This is PI."
    entry = _SchemaEntry(
        "pi", {"type": "float", "default": DEFAULT, "comment": COMMENT}
    )
    assert entry.default == approx(DEFAULT)
    assert entry.comment == COMMENT


### Check and convert test


def test_required_missing_value():
    entry = _SchemaEntry("mykey", {"type": "int", "required": True})
    err, msg, _ = entry.check_and_convert("")
    assert err
    assert msg and "required" in msg


def test_non_required_missing_value():
    entry = _SchemaEntry("mykey", {"type": "int", "required": False})
    err, _, val = entry.check_and_convert("")
    assert not err
    assert val is None


def test_bool_conversion_true():
    entry = _SchemaEntry("flag", {"type": "bool"})
    err, _, val = entry.check_and_convert("yes")
    assert not err
    assert val is True


def test_bool_invalid_string():
    entry = _SchemaEntry("flag", {"type": "bool"})
    err, msg, _ = entry.check_and_convert("maybe")
    assert err
    assert msg and "type error" in msg


def test_range_check_greater():
    entry = _SchemaEntry("num", {"type": "int", "max": 5})
    err, msg, _ = entry.check_and_convert("10")
    assert err
    assert msg and "greater" in msg


def test_range_check_lower():
    entry = _SchemaEntry("num", {"type": "float", "min": 5})
    err, msg, _ = entry.check_and_convert("4.99")
    assert err
    assert msg and "lower" in msg


def test_enum_check_not_str():
    entry = _SchemaEntry("choice", {"type": "int", "enum": [5, 3, 8]})
    err, msg, _ = entry.check_and_convert("5")
    assert err
    assert msg and "applicable" in msg


def test_enum_check_invalid():
    entry = _SchemaEntry("choice", {"type": "str", "enum": ["red", 8, "green"]})
    err, msg, _ = entry.check_and_convert("red")
    assert err
    assert msg and "string" in msg


def test_enum_check_unsupported():
    entry = _SchemaEntry("choice", {"type": "str", "enum": ["red", "green"]})
    err, msg, _ = entry.check_and_convert("yellow")
    assert err
    assert msg and "yellow" in msg


def test_enum_check_ok():
    entry = _SchemaEntry("choice", {"type": "str", "enum": ["red", "green"]})
    err, _, val = entry.check_and_convert("green")
    assert not err
    assert val == "green"


########################################################################
#                     Configuration parser test                        #
########################################################################


def test_generate_default_config():
    """
    Create a default configuration from a simple schema and compare
    the result with the expected configuration.
    """
    parser = ConfigParser(io.StringIO(TEST_SCHEMA), name="test-config")

    default_config = io.StringIO()
    parser.generate_default(default_config)

    default_config.seek(0)
    assert default_config.read() == TEST_CONFIG


def test_generate_config_not_existing(arrange_assets: None):
    """
    Check that the default configuration is created if the file is not
    existing.
    """
    config_path = Path(TEST_ASSETS_DST_FOLDER) / "test_config.ini"
    assert not config_path.exists()

    ConfigParser(io.StringIO(TEST_SCHEMA), str(config_path.resolve()))

    assert config_path.exists()

    with open(config_path, "r", encoding="utf-8") as file:
        assert file.read() == TEST_CONFIG


def test_read_config():
    """
    Parse and validate a configuration and read the values.
    """
    parser = ConfigParser(
        io.StringIO(TEST_SCHEMA), io.StringIO(TEST_CONFIG), name="test-config"
    )

    view = parser.get_view()
    assert view["section1"]["number"] == 8
    assert view["section1"]["flag"] == False
    assert view["section2"]["text"] == "This is a default text"
    assert view["section2"]["floating"] == approx(3.14)


def test_extra_section_raises():
    """
    Test that the configuration validation fails if it contains extra
    sections.
    """
    wrong_config = TEST_CONFIG + "[extra_section]\n"

    with pytest.raises(ConfigError, match="\\+extra_section"):
        ConfigParser(
            io.StringIO(TEST_SCHEMA), io.StringIO(wrong_config), name="test-config"
        )


def test_extra_key_raises():
    """
    Test that the configuration validation fails if it contains extra
    keys.
    """
    wrong_config = []
    for line in TEST_CONFIG.splitlines():
        wrong_config.append(line)
        if "[section2]" in line:
            wrong_config.append("random_key = 58")
    wrong_config = "\n".join(wrong_config)

    with pytest.raises(ConfigError, match="\\+random_key"):
        ConfigParser(
            io.StringIO(TEST_SCHEMA), io.StringIO(wrong_config), name="test-config"
        )


def test_invalid_type_raises():
    """
    Test that the configuration validation fails if a value has not the
    expected type.
    """
    wrong_config = []
    for line in TEST_CONFIG.splitlines():
        if "flag = false" in line:
            wrong_config.append('flag = "maybe"')
        else:
            wrong_config.append(line)
    wrong_config = "\n".join(wrong_config)

    with pytest.raises(ConfigError, match="type error"):
        ConfigParser(
            io.StringIO(TEST_SCHEMA), io.StringIO(wrong_config), name="test-config"
        )


def test_set_value():
    """
    Change a value and verify it is reflected in the previously retrieved
    view.
    """
    parser = ConfigParser(
        io.StringIO(TEST_SCHEMA), io.StringIO(TEST_CONFIG), name="test-config"
    )

    view = parser.get_view()

    parser.set_value("section2", "floating", 4.68)
    assert view["section2"]["floating"] == approx(4.68)


def test_set_value_file(arrange_assets: None):
    """
    Change a value and verify it has been written in the configuration
    file (.ini).
    """
    config_path = Path(TEST_ASSETS_DST_FOLDER) / "test_config.ini"

    parser = ConfigParser(io.StringIO(TEST_SCHEMA), str(config_path.resolve()))
    parser.set_value("section2", "floating", 4.68)

    content = TEST_CONFIG.replace("floating = 3.14", "floating = 4.68")
    with open(config_path, "r", encoding="utf-8") as file:
        assert file.read() == content


def test_set_value_missing_key_raises():
    """
    Check that trying to set a value for a missing key raises.
    """
    parser = ConfigParser(
        io.StringIO(TEST_SCHEMA), io.StringIO(TEST_CONFIG), name="test-config"
    )

    with pytest.raises(ConfigError, match="key"):
        parser.set_value("section1", "unexisting", True)


def test_set_wrong_value_raises():
    """
    Check that trying to set a value that doesn't match the schema rules
    raises.
    """
    parser = ConfigParser(
        io.StringIO(TEST_SCHEMA), io.StringIO(TEST_CONFIG), name="test-config"
    )

    with pytest.raises(ConfigError, match="schema rules"):
        # This parameter must be greater than 2.0
        parser.set_value("section2", "floating", 1.5)
