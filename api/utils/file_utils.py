import os
from pathlib import Path
import datetime
import re

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