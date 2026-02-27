"""FastAPI dependency injection functions for database connections."""
from typing import Generator
from db import FileDB, ConversionDB, ConversionRelationsDB, SettingsDB


def get_file_db() -> Generator[FileDB, None, None]:
    """Dependency that provides a FileDB instance and ensures cleanup."""
    db = FileDB()
    try:
        yield db
    finally:
        db.close()


def get_conversion_db() -> Generator[ConversionDB, None, None]:
    """Dependency that provides a ConversionDB instance and ensures cleanup."""
    db = ConversionDB()
    try:
        yield db
    finally:
        db.close()


def get_conversion_relations_db() -> Generator[ConversionRelationsDB, None, None]:
    """Dependency that provides a ConversionRelationsDB instance and ensures cleanup."""
    db = ConversionRelationsDB()
    try:
        yield db
    finally:
        db.close()


def get_settings_db() -> Generator[SettingsDB, None, None]:
    """Dependency that provides a SettingsDB instance and ensures cleanup."""
    db = SettingsDB()
    try:
        yield db
    finally:
        db.close()
