#!/bin/bash
# Synchronise l'addon installé sur l'appareil avec les blobs Git de HEAD (LF).
#
# Usage :
#   tools/device_sync.sh --dry-run   # compare et liste, ne pousse rien
#   tools/device_sync.sh             # pousse les différences, purge le bytecode
#
# Contenu déployable = `git archive HEAD` (les .gitattributes export-ignore
# s'appliquent). Ne pousse jamais le working tree : garantit du LF propre et
# évite qu'un fichier plus court laisse des débris en fin de fichier (un `rm`
# précède chaque `push`).
#
# Variables : ADDON_DIR (dossier de l'addon sur l'appareil), ADDON_ZIP_ROOT
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
DEV="${ADDON_DIR:-/sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/plugin.video.catchuptvandmore}"
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

command -v adb >/dev/null || { echo "adb requis" >&2; exit 1; }
adb get-state >/dev/null 2>&1 || { echo "aucun appareil adb connecté (adb connect <ip>)" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "== archive de HEAD (contenu déployable, LF) =="
git archive HEAD | tar -x -C "$TMP"

echo "== inventaire de l'appareil =="
adb shell "cd '$DEV' && find . -type f -exec md5sum {} \;" > "$TMP/device.md5"

python3 - "$TMP" <<'PY'
import hashlib
import os
import sys

tmp = sys.argv[1]


def md5(path):
    digest = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


push = []
device_only = []
seen = set()
for line in open(os.path.join(tmp, 'device.md5')):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    digest, path = line.split(None, 1)
    while path.startswith('./'):
        path = path[2:]
    if path.endswith(('.pyo', '.pyc')):
        continue
    seen.add(path)
    local = os.path.join(tmp, path)
    if not os.path.exists(local):
        device_only.append(path)
    elif md5(local) != digest:
        push.append(path)

missing = []
for dirpath, dirnames, filenames in os.walk(tmp):
    for name in filenames:
        rel = os.path.relpath(os.path.join(dirpath, name), tmp)
        if rel not in seen:
            missing.append(rel)

with open(os.path.join(tmp, 'to_push.txt'), 'w') as f:
    f.write('\n'.join(sorted(push)))
print('fichiers divergents (à pousser) : %d' % len(push))
print('fichiers présents seulement sur l\'appareil : %d' % len(device_only))
for path in sorted(device_only):
    print('  ' + path)
print('fichiers du dépôt absents de l\'appareil : %d' % len(missing))
for path in sorted(missing):
    print('  ' + path)
PY

if [ "$DRY" = 1 ]; then
    echo "(dry-run : rien poussé)"
    exit 0
fi

echo "== push (rm avant push, blobs Git) =="
mapfile -t FILES < "$TMP/to_push.txt"
N=0
for f in "${FILES[@]}"; do
    [ -z "$f" ] && continue
    adb shell "rm -f '$DEV/$f' '${DEV}/${f%.py}.pyc' '${DEV}/${f%.py}.pyo'" >/dev/null
    adb push "$TMP/$f" "$DEV/$f" >/dev/null
    N=$((N + 1))
    if [ $((N % 50)) -eq 0 ]; then echo "   ... $N"; fi
done
echo "poussés : $N"

echo "== purge bytecode (.pyo/.pyc) =="
adb shell "find '$DEV' -name '*.pyo' -exec rm -f {} \; ; find '$DEV' -name '*.pyc' -exec rm -f {} \;"

echo "== vérification md5 =="
adb shell "cd '$DEV' && find . -type f -exec md5sum {} \;" > "$TMP/device_after.md5"
python3 - "$TMP" <<'PY'
import hashlib
import os
import sys

tmp = sys.argv[1]


def md5(path):
    digest = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


left = 0
for line in open(os.path.join(tmp, 'device_after.md5')):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    digest, path = line.split(None, 1)
    while path.startswith('./'):
        path = path[2:]
    if path.endswith(('.pyo', '.pyc')):
        continue
    local = os.path.join(tmp, path)
    if not os.path.exists(local) or md5(local) != digest:
        left += 1
        print('encore divergent : ' + path)
print('fichiers divergents restants : %d' % left)
sys.exit(1 if left else 0)
PY
echo "OK : l'appareil est identique à HEAD (hors bytecode)."
