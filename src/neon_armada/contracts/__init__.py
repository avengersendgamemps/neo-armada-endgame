"""Versioned integration contracts shared by the engine, agents and client.

This package is the only code the desktop client and the engine have in
common. It contains plain data models and (de)serialisation helpers; it never
imports the engine, the client, PySide6 or subprocess facilities.
"""
