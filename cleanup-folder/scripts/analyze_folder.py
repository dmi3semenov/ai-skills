#!/usr/bin/env python3
"""
Analyze a folder for cleanup opportunities.
Usage: python3 analyze_folder.py <folder-path>
Output: JSON to stdout
"""
import hashlib, json, os, re, sys

SUFFIX_PATTERN = re.compile(r'^(.*?)\s*\((\d+)\)(\.[^.]+)?$')
INSTALLER_EXTENSIONS = {'.dmg', '.pkg'}

def md5_file(fp, cs=8192):
    h = hashlib.md5()
    try:
        with open(fp, 'rb') as f:
            while True:
                chunk = f.read(cs)
                if not chunk: break
                h.update(chunk)
        return h.hexdigest()
    except: return None

def find_duplicates(folder):
    files = [e.name for e in os.scandir(folder) if e.is_file(follow_symlinks=False)]
    hashes = {}
    for n in files:
        m5 = md5_file(os.path.join(folder, n))
        if m5: hashes.setdefault(m5, []).append(n)
    out = []
    for m5, names in hashes.items():
        if len(names) < 2: continue
        for n in names:
            m = SUFFIX_PATTERN.match(n)
            if m:
                orig = m.group(1) + (m.group(3) or '')
                if orig in names:
                    sz = os.path.getsize(os.path.join(folder, n))
                    out.append({'file': n, 'original': orig, 'size': sz, 'md5': m5})
    out.sort(key=lambda x: -x['size'])
    return out

def find_installers(folder):
    out = []
    for e in os.scandir(folder):
        if not e.is_file(follow_symlinks=False): continue
        _, ext = os.path.splitext(e.name)
        if ext.lower() in INSTALLER_EXTENSIONS:
            out.append({'file': e.name, 'size': e.stat().st_size, 'type': ext.lower().lstrip('.')})
    out.sort(key=lambda x: -x['size'])
    return out

def find_app_bundles(folder):
    out = []
    for e in os.scandir(folder):
        if e.is_dir(follow_symlinks=False) and e.name.endswith('.app'):
            sz, cnt = 0, 0
            try:
                for r, ds, fs in os.walk(e.path):
                    for f in fs:
                        try: sz += os.path.getsize(os.path.join(r, f)); cnt += 1
                        except: pass
            except: pass
            out.append({'file': e.name, 'size': sz, 'file_count': cnt})
    out.sort(key=lambda x: -x['size'])
    return out

def fmt(sz):
    if sz >= 1073741824: return f"{sz/1073741824:.1f} GB"
    elif sz >= 1048576: return f"{sz/1048576:.1f} MB"
    elif sz >= 1024: return f"{sz/1024:.0f} KB"
    else: return f"{sz} B"

def main():
    if len(sys.argv) < 2: print("Usage: python3 analyze_folder.py <path>", file=sys.stderr); sys.exit(1)
    folder = sys.argv[1]
    if not os.path.isdir(folder): print(f"Error: '{ folder}' not a dir", file=sys.stderr); sys.exit(1)
    dups = find_duplicates(folder)
    inst = find_installers(folder)
    apps = find_app_bundles(folder)
    total = sum(1 for e in os.scandir(folder) if e.is_file(follow_symlinks=False))
    result = {'folder': folder, 'total_files': total,
        'duplicates': {'fount': len(dups), 'total_size': sum(d['size'] for d in dups), 'total_size_human': fmt(sum(d['size'] for d in dups)), 'items': dups},
        'installers': {'count': len(inst), 'total_size': sum(i['size'] for i in inst), 'total_size_human': fmt(sum(i['size'] for i in inst)), 'items': inst},
        'app_bundles': {'count': len(apps), 'total_size': sum(a['size'] for a in apps), 'total_size_human': fmt(sum(a['size'] for a in apps)), 'items': apps},
        'total_recoverable_size': fmt(sum(d['size'] for d in dups)+sum(i['size'] for i in inst)+sum(a['size'] for a in apps))}
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
