"""A cache for grid tool output to make CLI experience more snappy."""

from time import time
from cPickle import dumps

class CacheEntry(object):
    """An entry in the cache."""

    def __init__(self, value, creation_time=None, cache_time=60):
        self.value = value
        if creation_time is None:
            self.creation_time = time()
        self.cache_time = cache_time

    def is_valid(self):
        return (self.creation_time + self.cache_time) > time()

class Cache(object):
    """A simple cache for function calls."""

    def __init__(self, cache_time=60):
        """`cache_time` determines how long an entrz will be cached."""
        self.cache_time = cache_time
        self.cache = {}

    def clean_cache(self):
        """Remove old entries from the cache."""
        for key in self.cache.keys():
            if not self.cache[key].is_valid():
                del self.cache[key]

    def hash(self, *args, **kwargs):
        """Turn function parameters into a hash."""
        return hash(dumps( (args, kwargs) ))

    def get_entry(self, *args, **kwargs):
        """Get a valid entry from the cache or `None`."""
        key = self.hash(*args, **kwargs)
        if key in self.cache:
            entry = self.cache[key]
            if entry.is_valid():
                return entry
            else:
                return None
        else:
            return None

    def add_entry(self, value, *args, **kwargs):
        """Add an entry to the cache."""
        key = self.hash(*args, **kwargs)
        self.cache[key] = CacheEntry(value, cache_time=self.cache_time)

    def cached(self, function):
        """Decorator to turn a regular function into a cached one."""

        def cached_function(*args, **kwargs):
            entry = self.get_entry(*args, **kwargs)
            if entry is not None:
                return entry.value
            else:
                value = function(*args, **kwargs)
                self.add_entry(value, *args, **kwargs)
                return value

        return cached_function