# -*- coding: utf-8 -*-
import sys
import os

def fix_file(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    # Remove UTF-8 BOM
    if data.startswith(b'\\xef\\xbb\\xbf'):
        data = data[3:]
    # Remove UTF-16 LE BOM
    elif data.startswith(b'\\xff\\xfe'):
        data = data[2:]
    # Remove UTF-16 BE BOM
    elif data.startswith(b'\\xfe\\xff'):
        data = data[2:]
    with open(filepath, 'wb') as f:
        f.write(data)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python fix_encoding.py <file>")
        sys.exit(1)
    fix_file(sys.argv[1])