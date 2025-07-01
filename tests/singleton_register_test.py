#!/usr/bin/env python3
"""
File: singleton_register_test.py
Author: Bastian Cerf
Date: 02/06/2025
Description:
    Unit test of the singleton register module.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import pytest
import threading

# Internal libraries
from common.singleton_register import SingletonRegister


class MySingleton(SingletonRegister):
    """
    Simple singleton class used for unit tests.
    """

    def _setup(self, name: str, id: int = 0) -> None:
        self.name = name
        self.id = id
        self.setup_called = True


@pytest.fixture(autouse=True)
def reset_singletons():
    """
    Automatically clears singleton instances before each test.

    With autouse=True, this fixture is applied to every test function
    without needing to include it explicitly.
    """
    SingletonRegister._instances.clear()  # type: ignore


def test_singleton_behavior():
    """
    Verify that two calls to the singleton constructor return the same
    instance initialized with the arguments of the first call.
    """
    instance1 = MySingleton("Banane", id=5)
    instance2 = MySingleton("Pomme")

    assert instance1 is instance2

    assert instance1.name == "Banane"
    assert instance1.id == 5
    assert instance1.setup_called


def test_multiple_singletons():
    """
    Check that multiple subclasses of `SingletonRegister` (including indirect ones)
    each maintain their own singleton instance.
    """

    class SubSingleton(MySingleton):
        pass

    instance1 = MySingleton("Base")
    instance2 = SubSingleton("Sub")

    # Each class has its own unique singleton instance
    assert instance1 is not instance2

    # Repeated calls return the same instances
    assert instance1 is MySingleton()
    assert instance2 is SubSingleton()

    # Confirm correct initial setup was preserved
    assert instance1.name == "Base"
    assert instance2.name == "Sub"


def test_singleton_thread_safety():
    """
    Launch 10 threads that will access the singleton at the same time
    and verify they all have accessed the only instance.
    """
    results: list[MySingleton] = []

    def create_instance():
        instance = MySingleton("thread-safe")
        results.append(instance)

    threads = [threading.Thread(target=create_instance) for _ in range(10)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads should receive the same singleton instance
    assert all(inst is results[0] for inst in results)
