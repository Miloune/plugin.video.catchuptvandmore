#!/usr/bin/env python3
"""Construit le zip installable de l'addon, compatible minizip Kodi 18.

Pourquoi un script dédié : `zip` (Info-ZIP) sur le montage Windows produit des
entrées de répertoire en mode 0777 que le minizip de Kodi 18 sur Android refuse
(`Failed to unpack archive`). Et un zip sans AUCUNE entrée de répertoire casse
le VFS `zip://` de Kodi (`Failed to read .../addon.xml`).

Forme correcte (voir AGENTS.md) :
  * entrées de répertoire : S_IFDIR | 0755 (+ bit MS-DOS directory)
  * entrées de fichier     : S_IFREG | 0644
  * horodatage fixe (zip reproductible)

Le contenu vient de `git archive HEAD` : les `export-ignore` de
`.gitattributes` s'appliquent (tools/, docs/, .github/… exclus) et seuls des
blobs committés en LF sont embarqués.

Usage :
  python3 tools/build_zip.py [--output plugin.video.catchuptvandmore-<...>.zip]
"""
import argparse
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile

PKG_ROOT = "plugin.video.catchuptvandmore"
FIXED_TIME = (2024, 1, 1, 0, 0, 0)
DIR_MODE = 0o40755
FILE_MODE = 0o100644


def git(*args):
    out = subprocess.run(["git"] + list(args), check=True,
                         stdout=subprocess.PIPE).stdout
    return out.decode().strip()


def default_output():
    version = "unknown"
    try:
        with open("addon.xml", encoding="utf-8") as f:
            match = re.search(r'<addon[^>]*\sversion="([^"]+)"', f.read())
        if match:
            version = match.group(1)
    except OSError:
        pass
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    commit = git("rev-parse", "--short", "HEAD")
    return "%s-%s-%s-%s.zip" % (PKG_ROOT, version, branch, commit)


def add_dir(zf, arcname):
    info = zipfile.ZipInfo(arcname)
    info.date_time = FIXED_TIME
    info.external_attr = (DIR_MODE << 16) | 0x10
    info.compress_type = zipfile.ZIP_STORED
    zf.writestr(info, b"")


def add_file(zf, arcname, data):
    info = zipfile.ZipInfo(arcname)
    info.date_time = FIXED_TIME
    info.external_attr = FILE_MODE << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, data)


def build(output):
    with tempfile.TemporaryDirectory() as tmp:
        blob = subprocess.run(["git", "archive", "HEAD"], check=True,
                              stdout=subprocess.PIPE).stdout
        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
            try:
                tar.extractall(tmp, filter="data")
            except TypeError:  # Python < 3.12
                tar.extractall(tmp)

        dirs = [PKG_ROOT]
        files = []
        for dirpath, dirnames, filenames in os.walk(tmp):
            for name in dirnames:
                rel = os.path.relpath(os.path.join(dirpath, name), tmp)
                dirs.append(PKG_ROOT + "/" + rel.replace(os.sep, "/"))
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, tmp)
                files.append((full, PKG_ROOT + "/" + rel.replace(os.sep, "/")))

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            for directory in sorted(set(dirs)):
                add_dir(zf, directory + "/")
            for full, arcname in sorted(files):
                with open(full, "rb") as f:
                    add_file(zf, arcname, f.read())

    with zipfile.ZipFile(output) as zf:
        infos = zf.infolist()
        names = [i.filename for i in infos]
        if PKG_ROOT + "/addon.xml" not in names:
            raise SystemExit("zip invalide : addon.xml manquant")
        for info in infos:
            mode = info.external_attr >> 16
            if info.filename.endswith("/"):
                if mode != DIR_MODE:
                    raise SystemExit("zip invalide : %s en mode %o (attendu %o)"
                                     % (info.filename, mode, DIR_MODE))
            elif mode != FILE_MODE:
                raise SystemExit("zip invalide : %s en mode %o (attendu %o)"
                                 % (info.filename, mode, FILE_MODE))
    print("%s : %d entrées (%d dossiers, %d fichiers), %.1f Mo"
          % (output, len(infos), len(dirs), len(files),
             os.path.getsize(output) / 1024.0 / 1024.0))
    print("vérifier : zipinfo %s | grep '/$'   # dossiers en drwxr-xr-x" % output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "-o", default=None,
                        help="chemin du zip (défaut : %s-<version>-<branche>-<sha>.zip)"
                             % PKG_ROOT)
    args = parser.parse_args()
    output = args.output or default_output()
    build(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
