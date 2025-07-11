import configparser
import os

class ConfigLoader:
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

    def __call__(self, name, default=None, cast=None):
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

