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
from typing import Iterable, Type, Any, Optional, Callable, NamedTuple, TextIO, Tuple
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
#                         Internal helpers                             #
########################################################################


def _str_to_bool(s: str) -> bool:
    """
    Convert the given string to a bool, if possible.

    Raises:
        ValueError: string doesn't contain a valid boolean.
    """
    s = s.strip().lower()
    if s in {"true", "1", "yes", "on"}:
        return True
    elif s in {"false", "0", "no", "off"}:
        return False

    raise ValueError(f"Invalid boolean string: {s}")


def _value_to_str(value: Any) -> str:
    """
    Convert the given value to a string literal.

    Raises:
        ValueError: Conversion not possible.
    """
    if isinstance(value, (int, float, str)):
        return str(value)
    elif isinstance(value, bool):
        return "true" if value else "false"
    raise ValueError(f"Unkown type '{type(value).__name__}'")


class ConversionResult(NamedTuple):
    """
    Holds the conversion result returned by
    `_SchemaEntry.check_and_convert()`.

    The message is only available if `error` is `True` and the `value`
    only if `error` is `False`.
    """

    error: bool
    message: Optional[str]
    value: Optional[Any]


class _SchemaEntry:
    """
    A schema entry stores the parameters related to a key-value pair in
    the .ini file, as defined in the schema file. It parses the JSON
    inner-block for the pair and provides a method to validate and convert
    the value from the .ini file (str) to its expected type.
    """

    # Map the variable types with their converting function
    _CONV_MAP: dict[str, Callable[[str], Any]] = {
        "int": int,
        "float": float,
        "str": str,
        "bool": _str_to_bool,
    }

    def __init__(self, key: str, entry: dict[str, Any]):
        """
        Create and parse the schema entry.

        Args:
            key (str): The key of the key-value pair, used to improve
                logging.
            entry (dict[str, Any]): Entry from the JSON file.
        """
        self._key = key

        # Parse required field
        field = "type"
        if field not in entry:
            raise ConfigError(f"'{field}' field missing for key '{key}'.")

        if entry[field] not in self._CONV_MAP:
            raise ConfigError(f"Type '{entry[field]}' unrecognized for key '{key}'.")

        # Value type and str to type converting function
        self._vartype: str = entry[field]
        self._conv_func = self._CONV_MAP[self._vartype]

        # Parse optional fields
        self._required = self.__get_field(entry, "required", (bool,), False)
        self._default = self.__get_field(entry, "default", None, None)
        self._comment = self.__get_field(entry, "comment", (str,), None)
        self._min = self.__get_field(entry, "min", (int, float), None)
        self._max = self.__get_field(entry, "max", (int, float), None)

        # Check no extra entry exists
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
                f"Unrecognized field(s): '{', '.join(diff)}' for key '{key}'."
            )

    def __get_field(
        self,
        entry: dict[str, Any],
        field: str,
        vartypes: Optional[Tuple],
        default: Any,
    ) -> Any:
        """
        Parse a parameter from the JSON dictionary.

        Args:
            entry (dict[str, Any]): Parameters dictionary.
            field (str): Field to parse (key name).
            vartype (Optional[Tuple]): Expected value types or `None` if
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
        if not vartypes or isinstance(value, vartypes):
            return value

        raise ConfigError(
            f"Type error for field '{field}' in key '{self._key}': "
            f"'{value}' has been identified as a '{type(value).__name__}', "
            f"must be a {" or a ".join([f"'{t.__name__}'" for t in vartypes])}."
        )

    @property
    def default(self) -> Any:
        return self._default

    @property
    def comment(self) -> str:
        return self._comment

    def check_and_convert(self, value: str) -> ConversionResult:
        """
        Check the schema rules for the given value and convert it to
        its defined type.

        The returned value is a named tuple containing the conversion
        results.

        Args:
            value (str): Value to check and convert.

        Returns:
            ConversionResult:
            error (bool): `True` on error, `False` if the `value` is
                available.
            message (str): Error description if any.
            value (Any): Value converted to the type defined in the
                schema.
        """
        # Check requireness
        if not value:
            if self._required:
                return ConversionResult(True, "Value is required", None)
            else:
                # Value is missing and it's allowed
                return ConversionResult(False, None, None)

        # Check expected value type by trying to convert it
        try:
            value = self._conv_func(value)
        except ValueError:
            return ConversionResult(
                True,
                f"type error for value '{value}' of type "
                f"'{type(value).__name__}', '{self._vartype}' required",
                None,
            )

        # Check integer or float is in range
        if isinstance(value, (int, float)):
            if self._min is not None and value < self._min:
                return ConversionResult(
                    True, f"{value} is lower than {self._min}", None
                )
            if self._max is not None and value > self._max:
                return ConversionResult(
                    True, f"{value} is greater than {self._max}", None
                )

        # All checks passed, return casted value
        return ConversionResult(False, None, value)


########################################################################
#                  Configuration parser and validator                  #
########################################################################


class ConfigParser:
    """
    The `ConfigParser` class loads and validates a configuration file
    in the `.ini` format against a schema file in the `.json` format.
    It provides a view on the loaded data dictionary.
    """

    def __init__(
        self,
        schema: str | TextIO,
        config: Optional[str | TextIO] = None,
        name: Optional[str] = None,
        gen_default: bool = True,
    ):
        """
        Initialize configuration data from a configuration file (.ini)
        and validate it against the provided schema (.json).

        If the configuration is given as a path (str) and no file exists
        at this path, a default configuration is inferred from the schema
        and the file is created.

        It is possible, although uncommon, to leave the `config` argument
        empty. It will only load the schema. The configuration can always
        be loaded and validated in a second time using
        `load_and_check_config()`.

        Args:
            schema (str | TextIO): Path to the schema file (.json) or an
                already opened file-like object.
            config (str | TextIO | None): Path to the configuration file
                (.ini), an already opened file-like object or leave empty
                to only load the schema.
            name (Optional[str]): A name to identify the configuration.
                The config file path is used by default. Note this must
                be set if using file-like objects.
            gen_default (bool): When `True` and a path is given for the
                `config` argument, a default configuration file is
                generated if no file already exists at this path.

        Raises:
            ConfigError: Any error related to data parsing, validation,
                etc.
        """
        self._schema: dict[str, dict[str, _SchemaEntry]] = {}
        self._config = configparser.ConfigParser(interpolation=None)
        self._data: dict[str, dict[str, Any]] = {}

        self._config_path = config

        # Retrieve config name
        if not name:
            if not isinstance(config, str):  # If file-like or None
                raise ConfigError("A configuration name is required.")
            path = Path(config)
            self._name = path.name
        else:
            self._name = name

        self.__load_schema(schema)

        # Create a default configuration file if not existing
        if gen_default and isinstance(config, str) and not Path(config).exists():
            try:
                with open(config, "x+", encoding="utf-8") as file:
                    self.generate_default(file)

            except Exception as e:
                raise ConfigError(
                    "Error generating the default configuration file "
                    f"for '{self._name}'."
                ) from e

            logger.info(f"Initial configuration file setup under '{config}'.")

        if config:
            self.load_and_check_config(config)

    def __load_schema(self, source: str | TextIO):
        """
        Load the schema file (.json). Populate `self._schema` data
        structure.

        Args:
            path (str | TextIO): Path to the schema file or an already
                opened file-like object.

        Raises:
            ConfigError: Wrap any exception that may occur during json
                file opening and parsing.
        """
        try:
            if isinstance(source, str):
                with open(source, "r", encoding="utf-8") as file:
                    schema = json.load(file)
            else:
                schema = json.load(source)

        except FileNotFoundError:
            raise ConfigError(f"Schema file not found for '{self._name}'.")
        except OSError as e:
            raise ConfigError(f"OS error occurred opening '{self._name}'.") from e
        except json.JSONDecodeError as e:
            raise ConfigError(
                f"Schema parsing error occurred for '{self._name}'."
            ) from e
        except Exception as e:
            raise ConfigError(f"Exception occurred for '{self._name}'.") from e

        # Read the JSON data and populate the schema
        for section in schema.keys():
            self._schema[section] = {}
            for key in schema[section].keys():
                # Create a schema entry by key
                entry = _SchemaEntry(key, schema[section][key])
                self._schema[section][key] = entry

    def __load_config(self, source: str | TextIO):
        """
        Load the configuration file (.ini) into `self._config`.

        Args:
            path (str | TextIO): Path to the configuration file or an
                already opened file-like object.

        Raises:
            ConfigError: Wrap any error that may occur when opening or
                parsing the .ini file.
        """
        try:
            if isinstance(source, str):
                with open(source, encoding="utf-8") as file:
                    self._config.read_file(file)
            else:
                self._config.read_file(source)

        except configparser.Error as e:
            raise ConfigError(
                f"A parsing exception occurred opening '{self._name}'."
            ) from e
        except Exception as e:
            raise ConfigError(f"An error occurred reading '{self._name}'.") from e

    def load_and_check_config(self, source: str | TextIO):
        """
        Load the given configuration (.ini file or file-like) and validate
        it against the schema.

        Args:
            source (str | TextIO): Path to the configuration file (.ini)
                or an already opened file-like object.
        """
        self.__load_config(source)
        self.__validate_data()

    def generate_default(self, stream: TextIO, annotate: bool = True):
        """
        Create a default configuration file. The default values are
        inferred from the schema.

        Args:
            stream (TextIO): Stream to write the configuration into.
            annotate (bool): `True` to annotate the key-value pairs with
                comments from the schema.
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

        # Write to the stream
        config.write(stream, space_around_delimiters=True)

        # Annotate the freshly created file with help comments
        if annotate:
            self.__annotate_config(stream)

    def __annotate_config(self, stream: TextIO):
        """
        Read an INI file as plain text from a stream and insert comments
        for known keys.

        Args:
            stream (TextIO): Stream to write the comments into.
        """
        current_section = None
        out_lines = []

        # Iterate the whole file
        stream.seek(0)
        for line in stream:
            stripped = line.strip()

            # detect section headers
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped.strip("[]")

            # detect key=value lines
            elif "=" in stripped and current_section is not None:
                key = stripped.split("=", 1)[0].strip()
                # Retrieve the comment for this key
                comment = self._schema[current_section][key].comment
                if comment:
                    out_lines.append(f"; {comment}\n")  # insert before line

            # default: just copy
            out_lines.append(line)

        # Replace stream content with new lines
        # By definition, there are at least the same number of lines in
        # the new stream.
        stream.seek(0)
        stream.writelines(out_lines)

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
                result = entry.check_and_convert(config_val)
                if result.error:
                    raise ConfigError(
                        f"Value for key '{key}' in section '{section}' is invalid: "
                        f"{result.message}."
                    )

                # Put the converted value in the data map
                self._data[section][key] = result.value

    def __compare(self, model: Iterable[str], config: Iterable[str]) -> list[str]:
        """
        Compare two `Iterable` and returns the difference.
        """
        model = set(model)
        config = set(config)
        missing = [f"-{e}" for e in model - config]
        extra = [f"+{e}" for e in config - model]
        return missing + extra

    def get_view(self) -> MappingProxyType[str, MappingProxyType[str, Any]]:
        """
        Get a view dictionary on the configuration data.

        Returns:
            MappingProxyType: A read-only dictionary on configuration
                data.
        """
        # Wrap a copy of the outer dictionary and wrap the inner dictionaries.
        # Inner dictionaries reflect self._data changes, while outer dictionary
        # is a copy (adding / removing sections won't be reflected).
        return MappingProxyType(
            {
                section: MappingProxyType(values)
                for section, values in self._data.items()
            }
        )

    def set_value(self, section: str, key: str, value: Any):
        """
        Change a value in the configuration file (.ini). No section or
        key can be created and the provided value must fulfill the schema
        rules.

        Args:
            section (str): The section name.
            key (str): The key name.
            value (Any): The value to write.

        Raises:
            ConfigError: The section or the key doesn't exist or doesn't
                fulfill the schema rules.
        """
        if section not in self._config or key not in self._config[section]:
            raise ConfigError(
                f"Section '{section}' or key '{key}' doesn't exist in '{self._name}'."
            )

        try:
            value_str = _value_to_str(value)
        except ValueError:
            raise ConfigError(
                f"Cannot convert value '{value}' of type "
                f"'{type(value).__name__}' to a string literal."
            )

        # The value must validate the schema rules
        err, msg, _ = self._schema[section][key].check_and_convert(value_str)
        if err:
            raise ConfigError(
                f"The value '{value_str}' doesn't match the schema rules for "
                f"section '{section}' and key '{key}': {msg}."
            )

        # The value can be written in the configuration
        self._data[section][key] = value
        self._config.set(section, key, value_str)

        try:
            if isinstance(self._config_path, str):
                with open(self._config_path, "w+", encoding="utf-8") as file:
                    self._config.write(file, space_around_delimiters=True)
                    self.__annotate_config(file)
                    logger.info(f"Configuration saved under '{self._config_path}'.")

        except Exception as e:
            raise ConfigError(
                f"Error saving the configuration under '{self._config_path}'."
            ) from e
