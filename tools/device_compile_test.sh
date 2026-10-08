#!/bin/bash
# Compile tous les .py de l'addon installé avec le VRAI Python 2.7 de Kodi
# (service.py temporaire qui appelle compile()), puis restaure le service.py
# d'origine. Attrape ce qu'un audit Python 3 ne peut pas voir : syntaxe py2.7
# réelle, débris de déploiement, fichiers divergents du dépôt.
#
# Usage : tools/device_compile_test.sh
#   variables : ADDON_DIR, KODI_LOG, WAIT_BOOT (secondes, défaut 45)
set -euo pipefail

DEV="${ADDON_DIR:-/sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/plugin.video.catchuptvandmore}"
LOG="${KODI_LOG:-/sdcard/Android/data/org.xbmc.kodi/files/.kodi/temp/kodi.log}"
ACTIVITY="org.xbmc.kodi/.Splash"
WAIT_BOOT="${WAIT_BOOT:-45}"

command -v adb >/dev/null || { echo "adb requis" >&2; exit 1; }
adb get-state >/dev/null 2>&1 || { echo "aucun appareil adb connecté (adb connect <ip>)" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "== Test de compilation Python 2.7 sur l'appareil =="
adb shell "am force-stop org.xbmc.kodi" >/dev/null; sleep 3

echo "-- sauvegarde du service.py de l'appareil"
adb pull "$DEV/service.py" "$TMP/service.py" >/dev/null

cat > "$TMP/service_test.py" <<EOF
# -*- coding: utf-8 -*-
# TEMPORAIRE - test de compilation py2.7 (tools/device_compile_test.sh)
import os
from kodi_six import xbmc

BASE = '$DEV'

errors = []
count = 0
for dirpath, dirnames, filenames in os.walk(BASE):
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        count += 1
        p = os.path.join(dirpath, fn)
        try:
            f = open(p, 'rb')
            try:
                src = f.read()
            finally:
                f.close()
            compile(src, p, 'exec')
        except Exception as e:
            errors.append('%s: %s' % (p, e))

xbmc.log('DEVICE-COMPILE-TEST files=%d errors=%d' % (count, len(errors)), xbmc.LOGNOTICE)
for e in errors:
    xbmc.log('DEVICE-COMPILE-ERROR ' + e, xbmc.LOGNOTICE)
EOF

echo "-- démarrage de Kodi avec le service de test"
adb shell "rm -f '$LOG'"
adb shell "rm -f '$DEV/service.py' '$DEV/service.pyc' '$DEV/service.pyo'"
adb push "$TMP/service_test.py" "$DEV/service.py" >/dev/null
adb shell "am start -n $ACTIVITY" >/dev/null
echo "   attente ${WAIT_BOOT}s..."
sleep "$WAIT_BOOT"

RESULT="$(adb shell "grep 'DEVICE-COMPILE-TEST' '$LOG'" || true)"
ERRORS="$(adb shell "grep 'DEVICE-COMPILE-ERROR' '$LOG'" || true)"

echo "-- restauration du service.py d'origine"
adb shell "am force-stop org.xbmc.kodi" >/dev/null; sleep 3
adb shell "rm -f '$DEV/service.py' '$DEV/service.pyc' '$DEV/service.pyo'"
adb push "$TMP/service.py" "$DEV/service.py" >/dev/null
adb shell "find '$DEV' -name '*.pyo' -exec rm -f {} \; ; find '$DEV' -name '*.pyc' -exec rm -f {} \;"
adb shell "am start -n $ACTIVITY" >/dev/null

echo "== Résultat =="
if [ -z "$RESULT" ]; then
    echo "Pas de marqueur DEVICE-COMPILE-TEST dans le log : Kodi n'a pas démarré" >&2
    echo "ou le service n'a pas été exécuté (voir $LOG)." >&2
    exit 1
fi
echo "$RESULT"
if [ -n "$ERRORS" ]; then
    echo "$ERRORS"
    exit 1
fi
echo "OK : tous les .py compilent avec le Python 2.7 de Kodi."
