from django.core.cache.backends.base import BaseCache
import threading

from UltraDict import UltraDict

import logging
logger = logging.getLogger(__name__)


class UltraDictCache(BaseCache):
    """ A simple in-memory cache. """

    def __init__(self, location, params):
        super().__init__(params)
        # Persist cache through runs
        self._cache = UltraDict(name=location, auto_unlink=False)
        key_count = len(self._cache.keys())
        logger.debug(f'UltraDict cache loaded: key_count={key_count} location={location} params={params}')

    def get(self, key, default=None, version=None):
        key = self.make_key(key, version=version)
        with self._cache.lock:
            return self._cache.get(key, default)

    def set(self, key, value, timeout=None, version=None):
        key = self.make_key(key, version=version)
        with self._cache.lock:
            self._cache[key] = value

    def delete(self, key, version=None):
        key = self.make_key(key, version=version)
        with self._cache.lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self):
        with self._cache.lock:
            self._cache.clear()

    def add(self, key, value, timeout=None, version=None):
        key = self.make_key(key, version=version)
        with self._cache.lock:
            if key not in self._cache:
                self._cache[key] = value
                return True
        return False
