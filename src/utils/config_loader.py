import configparser
import os

class ConfigLoader:
    """
    Resolves configuration values for settings.py. Each lookup walks:

      1. the given namespace, if `if_not_in_ns` is passed (an existing
         assignment, e.g. in the project settings, wins) — for internal
         use by djultra's settings injection
      2. the environment variable of the same name
      3. the `[DEFAULT]` section of the INI file named by `config_file`
      4. the `default` argument

    Values from env/INI are strings and get cast based on the type of
    `default` (bool, int, float, comma-separated list); namespace values
    are returned as-is.

    Usage:

        config = ConfigLoader()
        config.config_file = config('CONFIG_FILE', default='/dev/null')

        DEBUG = config('DEBUG', default=True)

    The config file is the per-environment layer: each environment (dev,
    prod, ...) can ship an INI with its non-secret values and point
    CONFIG_FILE at it, while secrets and ad-hoc overrides stay in
    environment variables, which always win over the file.
    """

    _config_cache = {}

    def __init__(self, config_file=None):
        self.config_file = config_file

    def _load_config_file(self):
        if self.config_file and self.config_file not in ConfigLoader._config_cache:
            if os.path.exists(self.config_file):
                config = configparser.ConfigParser()
                config.read(self.config_file)
                ConfigLoader._config_cache[self.config_file] = config['DEFAULT'] if 'DEFAULT' in config else {}
            else:
                ConfigLoader._config_cache[self.config_file] = {}

    def __call__(self, name, default=None, cast=None, if_not_in_ns=None):
        # An existing definition in the given namespace (e.g. globals()) wins;
        # the env/config-file/default chain below only fills what is not yet
        # defined. Namespace values are real Python objects, no casting needed.
        if if_not_in_ns is not None and name in if_not_in_ns:
            return if_not_in_ns[name]

        # Step 1: Look for the 'name' in environment variables
        value = os.environ.get(name)

        # Step 2: If 'name' is not in os.environ, load the config file if available
        if value is None:
            self._load_config_file()
            value = ConfigLoader._config_cache.get(self.config_file, {}).get(name)

        if value is not None:
            # Step 3a: If a value is found and a cast is callable, cast the value and return it
            if callable(cast):
                return cast(value)
            # Step 3b: If cast is not set but default is, determine type from default and cast
            elif default is not None:
                if isinstance(default, bool):
                    return value.lower() in ('true', 'True', 'TRUE', '1', 'yes', 'Yes', 'YES', 'on', 'On', 'ON')
                elif isinstance(default, int):
                    return int(value)
                elif isinstance(default, float):
                    return float(value)
                elif isinstance(default, list):
                    # Assuming a comma-separated list in env variable
                    return [part.strip() for part in value.split(',')]
                # If the default is not a common type, just return the value as a string
                return value
            # Step 3c: Return the string value if cast and default are not set
            else:
                return value

        # Step 4: If 'name' is not in os.environ or config file
        if default is not None:
            return default
        else:
            raise ValueError(f"Environment variable '{name}' is not set, and no default value provided.")

