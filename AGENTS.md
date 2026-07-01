# AGENTS.md

## Contexte matériel & contraintes de la cible

Ce fork est déployé sur un **projecteur Xiaomi (SoC Amlogic, ABI `arm`)** dont
l'environnement est **figé** et **ne peut pas être mis à jour** :

- **OS** : Android **6.0.1** (build `MHC19J`, `Xiaomi/batman`).
- **Kodi** : **18.9 (Leia)** — dernière version fonctionnelle sur cet appareil.
  Les versions 19+ (Matrix) ne sont pas compatibles avec ce matériel.
- **Interpréteur Python** : **Python 2.7** (Kodi 18 embarque CPython 2.7 ;
  Kodi 19+ seulement embarque Python 3).

> En résumé : on est **strictement bloqué sur Android 6 / Kodi 18.9 / Python 2.7**.
> Ce sont des contraintes dures, non négociables. Tout le code de ce dépôt doit
> rester exécutable tel quel par l'interpréteur Python 2.7 de Kodi 18.9.

## Règles de compatibilité Python 2.7 (OBLIGATOIRES)

Le projet amont (`Catch-up-TV-and-More`) cible désormais Kodi 19+/Python 3 et
introduit régulièrement de la syntaxe Python 3 uniquement. Ce fork doit
**systématiquement** rétro-porter ce code. Interdictions et substitutions :

| Interdit (Python 3.x)                          | À utiliser à la place (Python 2.7)                        |
| ---------------------------------------------- | --------------------------------------------------------- |
| f-strings : `f"{x}"`                           | `"{}".format(x)` ou `"%s" % x`                             |
| `yield from iterable`                          | `for _i in iterable: yield _i`                             |
| Annotations : `def f(x: int) -> str:` / `x: T` | Supprimer les annotations (signatures nues)                |
| `from __future__ import annotations`           | interdit (PEP 563, Python 3.7+)                            |
| `@dataclass` / `dataclasses`                   | classe simple avec `__init__` explicite                    |
| `from enum import Enum`                         | classe avec constantes entières (pas d'`enum34` sur Kodi18)|
| `async` / `await` / `nonlocal`                 | interdits (pas de support Python 2.7)                      |
| `return <valeur>` dans un générateur (fct avec `yield`) | **SyntaxError py2.7**. Voir règle ci-dessous.       |
| union type `int \| float`                      | interdit (Python 3.10+, dans les annotations)              |
| `match_obj[1]` (subscript d'un match regex)    | `match_obj.group(1)` (le subscript est Python 3.6+)        |
| `str.split(sep, maxsplit=N)` (mot-clé)         | `str.split(sep, N)` (positionnel)                          |
| `time.monotonic()`                             | `getattr(time, 'monotonic', time.time)()` (py3.3+ sinon)   |
| `datetime.timezone` / `timezone.utc`           | `pytz` / `pytz.UTC` (dépendance `script.module.pytz`)      |
| `datetime.timestamp()`                         | `calendar.timegm(dt.utctimetuple())` ou `time.time()`      |
| `zoneinfo` / `backports.zoneinfo`              | `pytz.timezone(name)` en fallback                          |
| `html.unescape(s)`                             | fallback `HTMLParser().unescape` (py2 : module `HTMLParser`)|
| `import urllib.parse/request/error` (bare)     | bloc `try/except ImportError` (py2 : `urllib`/`urllib2`/`urlparse`) |
| `import http.cookiejar` (bare)                 | `try/except` → py2 : `cookielib`                           |
| `with opener.open(url) as r:` (urllib opener)  | `r = opener.open(url)` + `try/finally: r.close()`          |
| `xbmcvfs.translatePath(...)`                   | `xbmc.translatePath(...)` (l'API Kodi 18)                  |
| `xbmcvfs.makeLegalFilename(...)`               | `xbmc.makeLegalFilename(...)` (l'API Kodi 18)              |

> Note : `str.split`/`rsplit` **avec `maxsplit=`** en mot-clé et le **subscript
> d'un objet match** (`m[1]`) sont invisibles à un simple grep de f-strings ;
> utiliser l'audit AST (voir plus bas) qui les détecte de façon fiable.

### Règle spéciale : `return <valeur>` dans un générateur

En Python 2.7, un `return` **avec valeur** dans une fonction qui contient un
`yield` lève `SyntaxError: 'return' with argument inside generator`. C'est
autorisé en Python 3.3+ (valeur de `StopIteration`), donc **invisible** pour un
compilateur Python 3 — seul l'audit AST le détecte (`tools/py27_audit.py`).

Conversion selon le contexte (⚠️ ne pas transformer un résolveur en générateur) :

- **Fonction `@Route.register`** (menu) — sortie anticipée « menu vide » :
  ```python
  yield False
  return
  ```
- **Sortie après avoir déjà `yield` des items**, ou **helper appelé dans une
  boucle** (produire « rien » pour cette entrée) :
  ```python
  return          # bare return, surtout PAS 'yield False'
  ```
- **Fonction `@Resolver.register`** qui **retourne une valeur** (URL, Listitem…) :
  elle **ne doit pas** contenir de `yield`. Garder `return <valeur>` /
  `return False` tel quel (valide car ce n'est pas un générateur).

### Infrastructure de compatibilité déjà en place

Le code s'appuie déjà sur ces briques — les conserver et les utiliser :

- `from __future__ import unicode_literals` en tête de chaque module.
- `from builtins import ...` (fourni par `script.module.future`).
- `kodi_six` pour envelopper les modules `xbmc*` (gestion unicode py2/py3).
- `script.module.six` pour les helpers de compatibilité.

### Dépendances `addon.xml` (bloc `<requires>`)

Ne déclarer **que** des modules disponibles pour Kodi 18 / Python 2.7. Une
dépendance non satisfaite empêche **toute l'installation** de l'addon
(`CAddonInstallJob: The dependency on ... could not be satisfied`).

- ❌ **Ne pas** déclarer `script.module.backports.zoneinfo` : ce module exige
  Python 3.6+ et n'existe pas sur Kodi 18. Il a été **retiré** de `addon.xml`.
  Le fallback `pytz` de `resources/lib/py_utils.py` couvre le besoin (`ZoneInfo`).
- ✅ Modules OK sur l'appareil : `codequick`, `youtube.dl`, `requests`, `pytz`,
  `inputstreamhelper`, `six`, `pyqrcode`, `tzlocal`, `future`, `kodi-six`,
  `resource.images.catchuptvandmore`.

## Vérification avant packaging

Aucun binaire Python 2 n'est requis pour valider la syntaxe. La méthode fiable
est un **audit basé sur l'AST de Python 3** qui détecte tous les nœuds Python 3
uniquement (`JoinedStr`/f-strings, `YieldFrom`, `AnnAssign` et annotations de
fonction, `NamedExpr`/walrus, `async`, `nonlocal`, `from __future__ import
annotations`, etc.).

```sh
# Doit afficher « 0 issue(s) » :
python3 tools/py27_audit.py .
```

En complément, quelques greps ciblés :

```sh
rg -n "(?:^|[^A-Za-z0-9_])f[\"'][^\"']*\{" --type py .   # f-strings
rg -n "yield from" --type py .                            # yield from
rg -n "xbmcvfs\.translatePath" --type py .                # API Kodi 19+
rg -n "\.timestamp\(\)|timezone\.utc" --type py .         # datetime py3
```

> Les `SyntaxWarning: invalid escape sequence` (regex sans préfixe `r''`) ne
> sont **pas** des erreurs : ces chaînes fonctionnent sur Python 2.7. Ne pas
> les « corriger » sauf demande explicite (bruit de diff massif).

## Packaging & déploiement

- Le plugin se package en `.zip` (structure `plugin.video.catchuptvandmore/...`).

> ⚠️ **Construire le zip avec Python `zipfile`, pas avec Info-ZIP `zip`.**
> Le minizip embarqué de Kodi 18 sur Android échoue à décompresser
> (`ERROR: Failed to unpack archive`) les zips produits par `zip` quand leurs
> **entrées de répertoire** portent des modes Unix `0777` (venant du montage
> Windows `/mnt/d`).
>
> Deux écueils, tous deux à éviter :
> 1. Entrées de répertoire en `0777` → `Failed to unpack archive`.
> 2. **Aucune** entrée de répertoire (que des fichiers) → le VFS `zip://` de
>    Kodi ne peut plus traverser le dossier → `Failed to read .../addon.xml`.
>
> La forme correcte : **inclure les entrées de répertoire** avec le mode
> `S_IFDIR | 0755`, et les fichiers en `0644`.
>
> Un exemple de script se trouve hors dépôt (`/tmp/opencode/build_zip.py`) ;
> l'essentiel :
>
> ```python
> import os, zipfile
> with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
>     for d in sorted(dir_arcs):                       # dossiers d'abord
>         zi = zipfile.ZipInfo(d + "/")
>         zi.date_time = (2024, 1, 1, 0, 0, 0)
>         zi.external_attr = (0o40755 << 16) | 0x10     # dir 0755
>         zf.writestr(zi, b"")
>     for full, arc in files:                           # puis les fichiers
>         zi = zipfile.ZipInfo(arc.replace(os.sep, "/"))
>         zi.date_time = (2024, 1, 1, 0, 0, 0)
>         zi.external_attr = (0o100644 << 16)           # file 0644
>         zi.compress_type = zipfile.ZIP_DEFLATED
>         zf.writestr(zi, open(full, "rb").read())
> ```
>
> Vérifications :
> - `zipinfo <zip> | grep '/$'` → dossiers en `drwxr-xr-x` (jamais `drwxrwxrwx`).
> - Tester sur l'appareil avant install :
>   `adb shell "busybox unzip -p <dev_zip> plugin.video.catchuptvandmore/addon.xml | head -2"`

- Exclure du zip les fichiers de dev (comme `.gitattributes export-ignore` +
  `AGENTS.md`, `tools/`, `.git/`).
- Déploiement sur l'appareil via ADB en réseau (supprimer l'ancien fichier et
  purger `addons/temp/` avant, pour éviter un `ls`/extraction obsolète) :

```sh
adb connect 192.168.1.231
adb shell "rm -rf /sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/temp/*"
adb shell "rm -f /sdcard/Download/<zip>"
adb push <zip> /sdcard/Download/
# Vérifier l'intégrité par md5 des deux côtés, puis dans Kodi :
# Extensions > Installer depuis un fichier zip
```

- Les fichiers de l'addon installé se trouvent sur l'appareil dans :
  `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/plugin.video.catchuptvandmore/`

## Note sur les fins de ligne

Le dépôt est monté depuis un volume Windows (`/mnt/d/...`). `git status` peut
signaler l'ensemble des fichiers comme « modifiés » à cause d'une conversion
CRLF ↔ LF. Ces différences sont du bruit (vérifiable avec
`git diff --ignore-all-space`) et ne doivent pas être confondues avec les
modifications fonctionnelles de rétro-portage.
