#!/usr/bin/env python3
"""
File: config_parser.py
Author: Bastian Cerf
Date: 12/08/2025
Description:
    Read and parse a configuration file in the .ini format. The file
    data is validated against a provided JSON schema. A default .ini
    file can be automatically created from the schema if non-existent.

    The .ini file is organized in sections containing key-value pairs.
    The JSON schema reflects this structure by declaring one block by
    section and one inner-block by key-value pair. This inner-block
    contains information such as the value type, default value and
    constraints.

    Supported key-value pair parameters:
    - type: the value type as int, float, str or bool
    - required: tells if the value is required or can be empty, notes that
        the key cannot be missing
    - default: the default value used when creating the default .ini file
        from the schema (JSON) file
    - comment: optional comment to add before the key-value pair when
        creating the default .ini file
    - min/max: optionally constrains int and float values in a specified
        range
    Only the type parameter is absolutely required.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
import json
import configparser
from pathlib import Path
from typing import Iterable, Type, Any, Optional, Callable
from types import MappingProxyType

logger = logging.getLogger(__name__)


########################################################################
#                 Configuration parser custom error                    #
########################################################################


class ConfigError(Exception):
    """
    General configuration file error. It's the only error raised by this
    module.
    """

    def __init__(self, msg: str):
        super().__init__(msg)


########################################################################
#                         Internal class(es)                           #
########################################################################


class _SchemaEntry:
    """
    A schema entry stores the parameters related to a key-value pair in
    the .ini file, as defined in the schema file. It parses the JSON
    inner-block for the pair and provides a method to validate and convert
    the value from the .ini file (str) to its expected type.
    """

    @staticmethod
    def __str_to_bool(s: str) -> bool:
        """
        Convert the given string to a bool, if possible.

        Raises:
            ValueError: string doesn't contain a valid boolean.
        """
        if isinstance(s, bool):
            return s

        s = s.strip().lower()
        if s in {"true", "1", "yes", "on"}:
            return True
        elif s in {"false", "0", "no", "off"}:
            return False

        raise ValueError(f"Invalid boolean string: {s}")

    # Map the variable types with their converting function
    CONV_MAP: dict[str, Callable[[str], Any]] = {
        "int": int,
        "float": float,
        "str": str,
        "bool": __str_to_bool,
    }

    def __init__(self, key: str, entry: dict[str, Any]):
        """
        Create and parse the schema entry.

        Args:
            key (str): The key oof the key-value pair, used to improve
                logging.
            entry (dict[str, Any]): Entry from the JSON file.
        """
        self._key = key

        # Parse required field
        field = "type"
        if field not in entry:
            raise ConfigError(f"'{field}' field missing for key '{key}'.")

        if entry[field] not in self.CONV_MAP:
            raise ConfigError(f"Type '{entry[field]}' unrecognized for key '{key}'.")

        # Value type and str to type converting function
        self._vartype: str = entry[field]
        self._conv_func = self.CONV_MAP[self._vartype]

        # Parse optional fields
        self._required = self.__get_field(entry, "required", bool, False)
        self._default = self.__get_field(entry, "default", None, None)
        self._comment = self.__get_field(entry, "comment", str, None)
        self._min = self.__get_field(entry, "min", int, None)
        self._max = self.__get_field(entry, "max", int, None)

        # Check no extra entry exist
        diff = set(entry.keys()) - {
            "type",
            "required",
            "default",
            "comment",
            "min",
            "max",
        }

        if diff:
            raise ConfigError(
                f"Unrecognized field(s): '{", ".join(diff)}' for key '{key}'."
            )

    def __get_field(
        self,
        entry: dict[str, Any],
        field: str,
        vartype: Optional[Type],
        default: Any,
    ) -> Any:
        """
        Parse a parameter from the JSON dictionary.

        Args:
            entry (dict[str, Any]): Parameters dictionary.
            field (str): Field to parse (key name).
            vartype (Optional[Type]): Expected value type or `None` if
                any type can go.
            default (Any): Fallback value if the parameter doesn't exist
                in the dictionary.

        Returns:
            Any: Parsed and checked value or the default value.

        Raises:
            ConfigError: Type error for read value.
        """
        if field not in entry:
            return default

        # Read value and check its type
        value = entry[field]
        if not vartype or isinstance(value, vartype):
            return value

        raise ConfigError(
            f"Type error for field '{field}' in key '{self._key}': "
            f"'{value}' has been identified as a '{type(value).__name__}', "
            f"must be a '{vartype.__name__}'."
        )

    @property
    def default(self) -> Any:
        return self._default

    @property
    def comment(self) -> str:
        return self._comment

    def check_and_convert(self, value: str) -> tuple[Optional[str], Any]:
        """
        Check the schema rules for the given value and convert it to
        its defined type.

        The first argument returned is an optional string describing the
        error, if any. If `None`, the second argument is available and
        holds the converted value. Note that it can also be `None` if the
        value is missing and it's allowed by the rules.

        Args:
            value (str): Value to check and convert.

        Returns:
            Optional[str]: Error description or `None` on success.
            Any: Value converted to the type defined in the schema,
                `None` if the value is missing or an error occurred.
        """
        # Check requireness
        if not value:
            if self._required:
                return "value is required", None
            else:
                # Value is missing and it's allowed
                return None, None

        # Check expected value type by trying to convert it
        try:
            value = self._conv_func(value)
        except ValueError:
            return (
                f"type error for value '{value}' of type "
                f"'{type(value).__name__}', '{self._vartype}' required",
                None,
            )

        # Check integer or float is in range
        if isinstance(value, (int, float)):
            if self._min is not None and value < self._min:
                return f"{value} is less than {self._min}", None
            if self._max is not None and value > self._max:
                return f"{value} is greater than {self._max}", None

        # All checks passed, return casted value
        return None, value


########################################################################
#                  Configuration parser and validator                  #
########################################################################


class ConfigParser:
    """
    The `ConfigParser` class loads and validates a configuration file
    in the `.ini` format against a schema file in the `.json` format.
    It provides a view on the loaded data dictionary.
    """

    def __init__(self, schema_path: str, config_path: str):
        """
        Initialize configuration data from a configuration file (.ini)
        and validate it against the provided schema (.json).

        Args:
            schema_path (str): Path to the schema file (.json).
            config_path (str): Path to the configuration file (.ini).

        Raises:
            ConfigError: Any error related to data parsing, validation,
                etc.
        """
        self._schema: dict[str, dict[str, _SchemaEntry]] = {}
        self._config = configparser.ConfigParser(interpolation=None)
        self._data: dict[str, dict[str, Any]] = {}

        # Retrieve config name from path
        path = Path(config_path)
        self._name = path.name

        self.__load_schema(schema_path)

        # Create a default configuration file if non-existing
        if not path.exists():
            self.__create_config(config_path)

        self.__load_config(config_path)
        self.__validate_data()

    def __load_schema(self, path: str):
        """
        Load the schema file (.json). Populate `self._schema` data
        structure.

        Args:
            path (str): Path to schema file.

        Raises:
            ConfigError: Wrap any exception that may occur during json
                file opening and parsing.
        """
        try:
            with open(path, "r", encoding="utf-8") as file:
                schema = json.load(file)
        except FileNotFoundError:
            raise ConfigError(f"Schema file not found for {self._name}.")
        except OSError as e:
            raise ConfigError(f"OS error occurred opening {self._name}.") from e
        except json.JSONDecodeError as e:
            raise ConfigError(f"Schema parsing error occurred for {self._name}.") from e
        except Exception as e:
            raise ConfigError(f"Exception occurred for {self._name}.") from e

        # Read the JSON data and populate the schema
        for section in schema.keys():
            self._schema[section] = {}
            for key in schema[section].keys():
                # Create a schema entry by key
                entry = _SchemaEntry(key, schema[section][key])
                self._schema[section][key] = entry

    def __load_config(self, path: str):
        """
        Load the configuration file (.ini) into `self._config`.

        Args:
            path (str): Path to configuration file.

        Raises:
            ConfigError: Wrap any error that may occur when opening or
                parsing the .ini file.
        """
        try:
            with open(path, encoding="utf-8") as file:
                self._config.read_file(file)
        except configparser.Error as e:
            raise ConfigError(
                f"A parsing exception occurred opening '{self._name}'."
            ) from e
        except Exception as e:
            raise ConfigError(f"An error occurred reading '{self._name}'.") from e

    def __create_config(self, path: str):
        """
        Create a default configuration file. The default values are
        infered from the schema.

        Args:
            path (str): Configuration file path.
        """
        # Infer the initial configuration from the schema
        config = configparser.ConfigParser(interpolation=None)
        for section in self._schema.keys():
            config[section] = {}
            for key in self._schema[section].keys():
                default = self._schema[section][key]._default
                value = str("" if default is None else default)
                if isinstance(default, bool):
                    value = value.lower()
                config[section][key] = value

        # Create and write the default configuration file
        with open(path, "x") as file:
            config.write(file, space_around_delimiters=True)

        # Annotate the freshly created file with help comments
        self.__annotate_config(path)

        logger.info(f"Initial configuration file setup under '{path}'.")

    def __annotate_config(self, path: str):
        """
        Read an INI file as plain text and insert comments for known keys.
        Writes the result to path_out.

        Args:
            path (str): Path to file to insert comments in.
        """
        current_section = None
        out_lines = []

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()

                # detect section headers
                if stripped.startswith("[") and stripped.endswith("]"):
                    current_section = stripped.strip("[]")
                    out_lines.append(line)
                    continue

                # detect key=value lines
                if "=" in stripped and current_section is not None:
                    key = stripped.split("=", 1)[0].strip()
                    comment = self._schema[current_section][key].comment
                    if comment:
                        out_lines.append(f"; {comment}\n")  # insert before
                    out_lines.append(line)
                    continue

                # default: just copy
                out_lines.append(line)

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(out_lines)

    def __validate_data(self):
        """
        Validate the data from the configuration file (.ini) and populate
        the `self._data` dictionary with values converted to their defined
        type.
        """
        # Validate sections
        diff = self.__compare(self._schema.keys(), self._config.sections())
        if diff:
            raise ConfigError(
                f"'{self._name}' sections differ from model: {", ".join(diff)}."
            )

        for section in self._schema.keys():
            # Validate keys
            diff = self.__compare(
                self._schema[section].keys(), self._config[section].keys()
            )
            if diff:
                raise ConfigError(
                    f"'{self._name}' section [{section}] differs from model: "
                    f"{", ".join(diff)}."
                )

            self._data[section] = {}

            # Check and cast values
            for key, entry in self._schema[section].items():
                config_val = self._config[section][key]
                error, cast_val = entry.check_and_convert(config_val)
                if error:
                    raise ConfigError(
                        f"Value for key '{key}' in section '{section}' is invalid: "
                        f"{error}."
                    )

                # Put the converted value in the data map
                self._data[section][key] = cast_val

    def __compare(self, model: Iterable[str], config: Iterable[str]) -> list[str]:
        """
        Compare two `Iterable` and returns the difference.
        """
        model = set(model)
        config = set(config)
        missing = [f"-{e}" for e in model - config]
        extra = [f"+{e}" for e in config - model]
        return missing + extra

    def view(self) -> MappingProxyType[str, MappingProxyType[str, Any]]:
        """
        Get a view dictionary on the configuration data.

        Returns:
            MappingProxyType: A read-only dictionary on configuration
                data.
        """
        return MappingProxyType(
            {
                section: MappingProxyType(values)
                for section, values in self._data.items()
            }
        )
