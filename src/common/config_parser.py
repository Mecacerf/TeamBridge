#!/usr/bin/env python3
"""
File: config_parser.py
Author: Bastian Cerf
Date: 12/08/2025
Description:
    Read and parse a configuration file.

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


class ConfigError(Exception):
    """General configuration file error."""

    def __init__(self, msg: str):
        super().__init__(msg)


class _SchemaEntry:
    """ """

    @staticmethod
    def __str_to_bool(s: str) -> bool:
        """ """
        if isinstance(s, bool):
            return s

        s = s.strip().lower()
        if s in {"true", "1", "yes", "on"}:
            return True
        elif s in {"false", "0", "no", "off"}:
            return False

        raise ValueError(f"Invalid boolean string: {s}")

    CAST_MAP: dict[str, Callable[[str], Any]] = {
        "int": int,
        "float": float,
        "str": str,
        "bool": __str_to_bool,
    }

    def __init__(self, key: str, entry: dict[str, Any]):
        """ """
        # Parse required field
        field = "type"
        if field not in entry:
            raise ConfigError(f"'{field}' field missing for key '{key}'.")

        if entry[field] not in self.CAST_MAP:
            raise ConfigError(f"Type '{entry[field]}' unrecognized for key '{key}'.")

        self._vartype = entry[field]
        self._cast_func = self.CAST_MAP[entry[field]]

        self._required = self.__get_field(entry, key, "required", bool, False)
        self._default = self.__get_field(entry, key, "default", None, None)
        self._min = self.__get_field(entry, key, "min", int, None)
        self._max = self.__get_field(entry, key, "max", int, None)

        # Check no extra entry exist
        diff = set(entry.keys()) - {"type", "required", "default", "min", "max"}
        if diff:
            raise ConfigError(
                f"Unrecognized field(s): '{", ".join(diff)}' for key '{key}'."
            )

    def __get_field(
        self,
        entry: dict[str, Any],
        key: str,
        field: str,
        vartype: Optional[Type],
        default: Any,
    ):
        """ """
        if field not in entry:
            return default

        # Read value and check its type
        value = entry[field]
        if not vartype or isinstance(value, vartype):
            return value

        raise ConfigError(
            f"Type error for field '{field}' in key '{key}': "
            f"'{value}' has been identified as a '{type(value).__name__}', "
            f"must be a '{vartype.__name__}'."
        )

    @property
    def default(self) -> Any:
        return self._default

    def check_and_cast(self, value: str) -> tuple[Optional[str], Any]:
        """
        Returns:
            Optional[str]: Error description or `None` if no error.
            Any: Value casted to its type, as defined in the schema, or
                `None` if an error occurred.
        """
        # Check requireness
        if not value:
            if self._required:
                return "value is required", None
            else:
                # Value is missing and it's allowed
                return None, None

        # Check expected value type by trying to cast it
        try:
            value = self._cast_func(value)
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


class ConfigParser:
    """ """

    def __init__(self, schema_path: str, config_path: str):
        """ """
        self._schema: dict[str, dict[str, _SchemaEntry]] = {}
        self._data: dict[str, dict[str, Any]] = {}
        self._config = configparser.ConfigParser(interpolation=None)

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
        """ """
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
        """ """
        try:
            with open(path, encoding="utf-8") as file:
                self._config.read_file(file)
        except configparser.Error as e:
            raise ConfigError(
                f"A parsing exception occurred opening '{self._name}'."
            ) from e
        except Exception as e:
            raise ConfigError(f"An error occurred reading '{self._name}'.") from e

    def __create_config(self, config_path: str):
        """ """
        # Infer the initial configuration from the schema
        config = configparser.ConfigParser(interpolation=None)
        for section in self._schema.keys():
            config[section] = {}
            for key in self._schema[section].keys():
                default = self._schema[section][key]._default
                config[section][key] = str("" if default is None else default).lower()

        # Create and write the default configuration file
        with open(config_path, "x") as file:
            config.write(file, space_around_delimiters=True)

        logger.info(f"Initial configuration file setup under '{config_path}'.")

    def __validate_data(self):
        """ """
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
                error, cast_val = entry.check_and_cast(config_val)
                if error:
                    raise ConfigError(
                        f"Value for key '{key}' in section '{section}' is invalid: "
                        f"{error}."
                    )

                # Put the casted value in the data map
                self._data[section][key] = cast_val

    def __compare(self, model: Iterable[str], config: Iterable[str]) -> list[str]:
        """ """
        model = set(model)
        config = set(config)
        missing = [f"-{e}" for e in model - config]
        extra = [f"+{e}" for e in config - model]
        return missing + extra

    def view(self) -> MappingProxyType[str, MappingProxyType[str, Any]]:
        """ """
        # Return a view on the data dictionary
        return MappingProxyType(
            {
                section: MappingProxyType(values)
                for section, values in self._data.items()
            }
        )
