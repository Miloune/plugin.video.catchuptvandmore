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
>
> Limites de lecture des flux sur cette cible (ISA 2.4.8 / DRM) :
> [`docs/KODI18_LIMITATIONS.md`](docs/KODI18_LIMITATIONS.md) — en bref :
> DASH/CENC et HLS clair OK, HLS `SAMPLE-AES` non (RMC+ direct p. ex.).

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
> d'un objet match** (`m[1]`) sont invisibles à un simple grep de f-strings.
> `maxsplit=` et les API runtime py3 (`bytes(x, encoding=...)`,
> `open(..., encoding=)`, `str.removeprefix`, etc.) sont détectés par la couche
> « runtime » de `tools/py27_audit.py` ; le subscript `m[1]` reste à vérifier
> en relecture (l'AST ne suit pas le type de l'objet).

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

Aucun binaire Python 2 n'est requis pour valider la syntaxe. La référence est
`tools/py27_audit.py`, à deux couches :

1. **AST Python 3** : nœuds py3 uniquement (f-strings, `yield from`,
   annotations, walrus, `async`, `nonlocal`, `return <valeur>` dans un
   générateur, matmul, arguments keyword-only/position-only, starred
   assignment, `raise ... from`, `{**d}`, unpacking multiple, séparateurs
   numériques…).
2. **Contrôles runtime** (commentaires et chaînes masqués) : API py3 invisibles
   à l'AST (`bytes(x, encoding=...)`, `open(..., encoding=...)`,
   `str.removeprefix`, `maxsplit=`, exceptions py3, etc.) et imports
   `urllib.parse/request/error` + `http.cookiejar` non gardés par un
   `try/except ImportError`.

```sh
# Doit afficher « 0 issue(s) » :
python3 tools/py27_audit.py .
```

Le hook `pre-commit` l'exécute à chaque commit
(`tools/install_git_hooks.sh` à lancer une fois) et le workflow
`.github/workflows/py27.yml` en CI. Le subscript d'un objet match (`m[1]`,
py3.6+) reste à vérifier en relecture : l'AST ne suit pas le type de l'objet.

> Les `SyntaxWarning: invalid escape sequence` (regex sans préfixe `r''`) ne
> sont **pas** des erreurs : ces chaînes fonctionnent sur Python 2.7. Ne pas
> les « corriger » (l'audit les masque déjà).

## Synchronisation avec l'amont (merge + rétro-portage)

Pour récupérer les correctifs de `Catch-up-TV-and-More` (nouveaux fixes de
chaînes, etc.) tout en conservant les contraintes Python 2.7, **ne pas** cueillir
les commits un par un : **merger** la branche amont puis **re-porter** le code
Python 3 introduit. Procédure éprouvée :

1. **Sauvegarder les patches locaux propres au fork** avant de merger, car un
   conflit peut les écraser. En particulier le patch `preferred_video_codec`
   (dans `6play.py` et `resolver_proxy.py`). Générer un diff temporaire (hors
   dépôt) à réappliquer ensuite :

   ```sh
   git diff HEAD -- resources/lib/channels/fr/6play.py \
       resources/lib/resolver_proxy.py > /tmp/fork_patches.diff
   ```

2. **Récupérer et merger l'amont** (le remote `origin` pointe sur le dépôt
   upstream, `Miloune` sur le fork) :

   ```sh
   git fetch origin
   git merge --no-commit --no-ff origin/dev
   ```

   Le `--no-commit` permet d'auditer et de re-porter **avant** de figer le merge.

3. **Résoudre les conflits** en gardant à l'esprit la cible py2.7 :
   - Préférer la **version amont** pour la logique métier (nouveaux fixes), puis
     rétro-porter la syntaxe py3 qu'elle introduit (étape 5).
   - Garder la **version du fork (HEAD)** quand elle porte une adaptation Kodi 18
     déjà faite (ex. le garde `URLLIB3_VERSION` de `cnews.py`, les blocs
     `try/except ImportError` sur `urllib`).

4. **Réappliquer les patches du fork** sauvegardés à l'étape 1 (le diff temporaire
   n'est **pas** versionné — c'est un artefact de session) :

   ```sh
   git apply /tmp/fork_patches.diff   # ou réappliquer les hunks à la main
   ```

5. **Re-porter en Python 2.7** tout le code amont nouvellement introduit, en
   appliquant les règles du tableau ci-dessus. `tools/py27_audit.py` liste
   précisément les fichiers/lignes à corriger (imports `urllib` non gardés
   inclus) :

   ```sh
   python3 tools/py27_audit.py resources/     # -> corriger jusqu'à « 0 issue »
   ```

   Vérifier ensuite qu'aucun fichier supprimé par l'amont ne subsiste, puis
   valider sur l'appareil avec `tools/device_compile_test.sh` (syntaxe py2.7
   réelle) avant de committer.

6. **Committer le merge** en ne stageant **que** les fichiers effectivement
   touchés (résolutions de conflit + re-portages) :

   ```sh
   git add <fichiers modifiés> && git commit
   ```

> Un fichier **supprimé** par l'amont (ex. `weo.py`, `rmcbfmplay.py`) doit aussi
> être retiré de l'appareil (`.py`, **`.pyo`** et `.pyc`) lors du déploiement,
> sinon un module fantôme subsiste. Penser aussi à la playlist générée par IPTV
> Manager (`userdata/addon_data/service.iptv.manager/playlist.m3u8`) : elle
> embarque les anciennes routes et doit être patchée ou régénérée, sinon zapper
> la chaîne PVR produit `RouteMissing: unable to import route module: ...`.
>
> Garde de dépôt dans les workflows amont (`ci.yml`, `pr.yml`, `release.yml`) :
> le conserver au merge. Le pipeline du fork est `py27.yml`.

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
> Le script est versionné : `python3 tools/build_zip.py [--output <zip>]`
> (contenu `git archive HEAD`, entrées de répertoire 0755, fichiers 0644,
> vérification intégrée des modes).
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

### Déploiement incrémental (push direct des fichiers modifiés)

Pour un petit lot de fichiers (ex. après un merge), l'install par zip est
superflue : pousser directement les fichiers modifiés dans le dossier de l'addon
installé. **Toujours `rm -f` le fichier de l'appareil AVANT le `push`**, sinon un
fichier plus court laisse des débris en fin de fichier (déjà provoqué un
`IndentationError`). Pousser depuis les **blobs committés** (`git show <rev>:path`)
garantit du LF propre, sans bruit CRLF du montage Windows.

> Pour synchroniser tout l'arbre d'un coup (ou vérifier l'intégrité sans rien
> pousser), utiliser `tools/device_sync.sh --dry-run` puis
> `tools/device_sync.sh` : il compare HEAD à l'appareil, `rm`+push les
> différences et purge le bytecode.

```sh
DEV=/sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/plugin.video.catchuptvandmore
for f in <fichiers modifiés>; do
  adb shell "rm -f '$DEV/$f' '${DEV}/${f%.py}.pyc' '${DEV}/${f%.py}.pyo'"
  adb push "$f" "$DEV/$f"
done
# purger tous les .pyo et .pyc résiduels de l'arbre (Android find n'a pas
# -delete) — Kodi 18 écrit des .pyo, le rm préalable évite les débris :
adb shell "find '$DEV' -name '*.pyo' -exec rm -f {} \;"
adb shell "find '$DEV' -name '*.pyc' -exec rm -f {} \;"
adb shell "am force-stop org.xbmc.kodi" && sleep 2
adb shell "am start -n org.xbmc.kodi/.Splash"
```

Vérifier par `md5sum` des deux côtés, puis contrôler le log de démarrage
(`.kodi/temp/kodi.log`) — absence de `Traceback`/`SyntaxError`/`ImportError` et
version d'addon attendue dans les lignes `ADDON: ... installed`.

### Vérification par le vrai Python 2.7 (appareil)

`tools/device_compile_test.sh` compile tous les `.py` de l'addon installé avec
le Python 2.7 embarqué de Kodi (service.py temporaire + `compile()`), puis
restaure le service.py d'origine. À lancer après un merge/déploiement : il
attrape la syntaxe py2.7 réelle, y compris ce que l'AST Python 3 ne voit pas.

> ⚠️ Les `settings.xml` de `addon_data/` (et leurs backups `.bak-*`) contiennent
> les identifiants en clair : ne jamais faire de `grep -r` sur `userdata` (les
> valeurs finissent dans les logs/transcriptions). Contrôler par filtre
> `SET`/`EMPTY` sans afficher les valeurs.
