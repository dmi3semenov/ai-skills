#!/usr/bin/env python3
"""
Analyze a folder for cleanup opportunities:
- True duplicate files (same MD5, differ only by copy suffix)
- Installer files (DMG, PKG)
- App bundles (.app directories)

Usage: python3 analyze_folder.py <folder-path>
Output: JSON to stdout
"""

import hashlib
import json
import os
import re
import sys


SUFFIX_PATTERN = re.compile(r'^(.*?)\s*\((\d+)\)(\.[^.]+)?$')
INSTALLER_EXTENSIONS = {'.dmg', '.pkg'}


def md5_file(filepath, chunk_size=8192):
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


def find_duplicates(folder):
    """Find files that are true duplicates: same MD5 + name differs only by suffix like (1), (2)."""
    # Collect all files
    files = []
    for entry in os.scandir(folder):
        if entry.is_file(follow_symlinks=False):
            files.append(entry.name)

    # Compute hashes
    hashes = {}
    for name in files:
        path = os.path.join(folder, name)
        md5 = md5_file(path)
        if md5:
            hashes.setdefault(md5, []).append(name)

    # Find groups with duplicates
    duplicates_to_delete = []
    for md5, names in hashes.items():
        if len(names) < 2:
            continue

        # For each file with a suffix pattern, check if the original exists in the same group
        for name in names:
            m = SUFFIX_PATTERN.match(name)
            if m:
                base = m.group(1)
                ext = m.group(3) or ''
                original = base + ext

                if original in names:
                    size = os.path.getsize(os.path.join(folder, name))
                    duplicates_to_delete.append({
                        'file': name,
                        'original': original,
                        'size': size,
                        'md5': md5
                    })

    # Sort by size descending
    duplicates_to_delete.sort(key=lambda x: -x['size'])
    return duplicates_to_delete


def find_installers(folder):
    """Find DMG and PKG files, including extensionless copies."""
    installers = []

    for entry in os.scandir(folder):
        if not entry.is_file(follow_symlinks=False):
            continue

        name = entry.name
        _, ext = os.path.splitext(name)

        if ext.lower() in INSTALLER_EXTENSIONS:
            size = entry.stat().st_size
            installers.append({
                'file': name,
                'size': size,
                'type': ext.lower().lstrip('.')
            })

    # Sort by size descending
    installers.sort(key=lambda x: -x['size'])
    return installers


def find_app_bundles(folder):
    """Find .app directories."""
    apps = []

    for entry in os.scandir(folder):
        if entry.is_dir(follow_symlinks=False) and entry.name.endswith('.app'):
            # Calculate total size
            total_size = 0
            file_count = 0
            try:
                for root, dirs, files in os.walk(entry.path):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            total_size += os.path.getsize(fp)
                            file_count += 1
                        except OSError:
                            pass
            except OSError:
                pass

            apps.append({
                'file': entry.name,
                'size': total_size,
                'file_count': file_count
            })

    apps.sort(key=lambda x: -x['size'])
    return apps


def format_size(size_bytes):
    """Human-readable file size."""
    if size_bytes >= 1073741824:
        return f"{size_bytes / 1073741824:.1f} GB"
    elif size_bytes >= 1048576:
        return f"{size_bytes / 1048576:.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    else:
        return f"{size_bytes} B"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_folder.py <folder-path>", file=sys.stderr)
        sys.exit(1)

    folder = sys.argv[1]

    if not os.path.isdir(folder):
        print(f"Error: '{folder}' is not a directory", file=sys.stderr)
        sys.exit(1)

    duplicates = find_duplicates(folder)
    installers = find_installers(folder)
    app_bundles = find_app_bundles(folder)

    total_files = sum(1 for e in os.scandir(folder) if e.is_file(follow_symlinks=False))

    result = {
        'folder': folder,
        'total_files': total_files,
        'duplicates': {
            'count': len(duplicates),
            'total_size': sum(d['size'] for d in duplicates),
            'total_size_human': format_size(sum(d['size'] for d in duplicates)),
            'items': duplicates
        },
        'installers': {
            'count': len(installers),
            'total_size': sum(i['size'] for i in installers),
            'total_size_human': format_size(sum(i['size'] for i in installers)),
            'items': installers
        },
        'app_bundles': {
            'count': len(app_bundles),
            'total_size': sum(a['size'] for a in app_bundles),
            'total_size_human': format_size(sum(a['size'] for a in app_bundles)),
            'items': app_bundles
        },
        'total_recoverable_size': format_size(
            sum(d['size'] for d in duplicates) +
            sum(i['size'] for i in installers) +
            sum(a['size'] for a in app_bundles)
        )
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()