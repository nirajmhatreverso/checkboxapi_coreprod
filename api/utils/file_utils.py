import os
from pathlib import Path
import datetime
import re
import logging
import pprint

logger = logging.getLogger('cmts_api')

def create_unique_file(base_path: str, prefix: str = "data_", extension: str = ".tmp") -> str:
    os.makedirs(base_path, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{prefix}{timestamp}{extension}"
    full_path = os.path.join(base_path, filename)
    Path(full_path).touch()
    return os.path.abspath(full_path)


def clean_text(s: str) -> str:
    s = s.replace('\x00', '')
    s = re.sub(r'[\x00-\x1F\x7F]', '', s)
    return s.strip()

def log_pretty(obj):
    # set up pretty printer
    pp = pprint.PrettyPrinter(indent=2, sort_dicts=False)
    pretty_out = f"{pp.pformat(obj)}"


def replace_new_line(s: str, lineseparator: str) -> str:
    return s.replace('\n', lineseparator)


def read_file_to_list(filename: str, strip_newlines: bool = True, encoding: str = 'utf-8') -> list:
    try:
        with open(filename, 'r', encoding=encoding) as f:
            if strip_newlines:
                return [line.strip() for line in f]
            return f.readlines()
    except Exception as e:
        print(f"Error reading file {filename}: {e}")
        return []

def replace_variables(command: str, variables: dict) -> str:
    # Normalize keys to lowercase to match {var} style
    #logger.info(f"variables: {command}")
    normalized = {k.upper(): v for k, v in variables.items()}
    
    try:
        return command.format(**normalized)
    except KeyError as e:
        logger.warning(f"No match found for variable: {e}")
        # Replace only found keys, leave missing ones as-is
        for key, value in normalized.items():
            command = command.replace(f'{{{key}}}', str(value))
            logger.info(f"variables: {command}")
        return command


def replace_ivariables(command: str, variables: dict) -> str:
    normalized = {k.upper(): v for k, v in variables.items()}

    # ✅ Unescape \$ → $ in case DB stores it escaped
    command = command.replace('\\$', '$')

    def replacer(match):
        key = match.group(1).upper()
        if key not in normalized:
            logger.warning(f"No match found for ${match.group(1)}")
        return str(normalized.get(key, match.group(0)))

    return re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', replacer, command)