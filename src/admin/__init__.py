# djultra/admin/__init__.py

import importlib
import pkgutil

import logging
logger = logging.getLogger(__name__)

__all__ = [
    module_name
    for _, module_name, _ in pkgutil.iter_modules(__path__)
]

for module_name in __all__:
    importlib.import_module(f"{__name__}.{module_name}")
