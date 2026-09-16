"""Test support: in-memory doubles for every port, shared across the suites.

Not part of the shipped package. ``src/ragcore`` contains no fakes, no stubs and no test hooks —
a production import path that can reach a double is a production import path that can be made to
use one.
"""
