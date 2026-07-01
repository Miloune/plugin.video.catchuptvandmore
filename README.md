# Catch-up TV & More

<p align="center">
  <img src="https://github.com/Catch-up-TV-and-More/plugin.video.catchuptvandmore/raw/dev/icon.png" alt="Catch-up TV & More logo">
</p>

![CI](https://github.com/Catch-up-TV-and-More/plugin.video.catchuptvandmore/workflows/CI/badge.svg?branch=dev)

## ⚠️ À propos de ce fork — *About this fork*

**Français** — Ce dépôt est un **fork destiné à une vieille version de Kodi**.
Il cible **Kodi 18.9 (Leia)**, qui embarque **Python 2.7**, sur un matériel figé
(par exemple un projecteur Xiaomi sous Android 6.0.1 qui ne peut pas être mis à
jour). Le projet amont ne supporte plus que Kodi 19+ / Python 3 et introduit
régulièrement de la syntaxe Python 3 uniquement (f-strings, `yield from`,
annotations, `return` valué dans un générateur, `datetime.timezone`,
`zoneinfo`, etc.). Ce fork rétro-porte tout ce code vers Python 2.7. Voir
[`AGENTS.md`](AGENTS.md) pour les règles de compatibilité détaillées et l'outil
d'audit [`tools/py27_audit.py`](tools/py27_audit.py).

*English* — This repository is a **fork for an old Kodi version**. It targets
**Kodi 18.9 (Leia)**, which ships **Python 2.7**, on frozen hardware (e.g. a
Xiaomi projector running Android 6.0.1 that cannot be upgraded). Upstream now
only supports Kodi 19+ / Python 3 and keeps introducing Python-3-only syntax;
this fork back-ports it all to Python 2.7. See [`AGENTS.md`](AGENTS.md) for the
compatibility rules and the [`tools/py27_audit.py`](tools/py27_audit.py)
auditor.

### Correctif SSL requis dans `script.module.codequick` — *Required SSL patch*

**Français** — Android 6.0.1 possède un magasin de certificats CA **trop ancien**
pour valider les certificats modernes (ex. `login.6play.fr`), ce qui provoque
`SSLError: CERTIFICATE_VERIFY_FAILED`. La correction ne se fait **pas** dans ce
dépôt mais dans la dépendance **`script.module.codequick`** (fichier
`lib/urlquick.py`). Il faut désactiver la vérification SSL dans la classe
`Session`.

Sur l'appareil, le fichier se trouve généralement ici :
`/sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/script.module.codequick/lib/urlquick.py`

*English* — Android 6.0.1 has a CA store that is **too old** to validate modern
certificates (e.g. `login.6play.fr`), causing
`SSLError: CERTIFICATE_VERIFY_FAILED`. The fix does **not** live in this repo but
in the **`script.module.codequick`** dependency (`lib/urlquick.py`): SSL
verification must be disabled in the `Session` class.

Diff à appliquer — *Patch to apply* (`script.module.codequick/lib/urlquick.py`) :

```diff
 class Session(sessions.Session):
     def __init__(self, cache_location=CACHE_LOCATION, **kwargs):  # type: (str, ...) -> None
         super(Session, self).__init__()
+        self.verify = False

         #: When set to True, This attribute checks if the status code of the
         #: response is between 400 and 600 to see if there was a client error
         #: or a server error. Raising a :class:`HTTPError` if so.
         self.raise_for_status = kwargs.get("raise_for_status", _DEFAULT_RAISE_FOR_STATUS)

         #: Age the 'cache' can be, before it’s considered stale. -1 will disable caching.
         #: Defaults to :data:`MAX_AGE <urlquick.MAX_AGE>`
         self.max_age = kwargs.get("max_age", MAX_AGE)

         self.cache_adapter = adapter = CacheHTTPAdapter(cache_location)
         self.mount("https://", adapter)
         self.mount("http://", adapter)

+    def merge_environment_settings(self, url, proxies, stream, verify, cert):
+        # Force-disable SSL certificate verification on this device.
+        # Android 6.0.1 (Kodi 18) ships an outdated CA store that cannot
+        # validate modern certificates (e.g. login.6play.fr), so we ignore
+        # any per-request verify=True and always disable verification.
+        settings = super(Session, self).merge_environment_settings(
+            url, proxies, stream, verify, cert)
+        settings["verify"] = False
+        return settings
+
     def _raise_for_status(self, response, raise_for_status):  # type: (Response, bool) -> None
```

> **Français** — `self.verify = False` fixe le défaut de la session ; l'override
> de `merge_environment_settings` garantit qu'un appel passant explicitement
> `verify=True` (comme `m3u8.py`) ne réactive pas la vérification. ⚠️ Désactiver
> la vérification SSL réduit la sécurité — c'est un compromis assumé pour ce
> matériel obsolète. Le correctif est à réappliquer après toute mise à jour du
> module `script.module.codequick`.
>
> *English* — `self.verify = False` sets the session default; the
> `merge_environment_settings` override ensures a caller passing explicit
> `verify=True` (like `m3u8.py`) cannot re-enable verification. ⚠️ Disabling SSL
> verification lowers security — an accepted trade-off for this legacy hardware.
> Re-apply the patch after any `script.module.codequick` update.

## Description
[Catch-Up TV & More](https://kodi.tv/addons/omega/plugin.video.catchuptvandmore) est un greffon vidéo pour le centre multimédia Kodi (ex XBMC).
Cette extension regroupe l'ensemble des vidéos des différents services et chaînes de rattrapage TV. De plus, cette extension vous permet d'accéder rapidement aux vidéos et contenus proposés par certains sites internet.
Catch-Up TV & More est compatible avec les versions de Kodi "19 Matrix" et supérieures.

*[Catch-Up TV & More](https://kodi.tv/addons/omega/plugin.video.catchuptvandmore) is a video addon for the Kodi media center (formerly XBMC).*
*This plugin brings together all the videos of various services and channels of catch-up TV. Furthermore, this addon allows you to quickly access the videos and content offered by certain websites.*
Catch-Up TV & More is compatible with Kodi "19 Matrix" and higher versions.

## Comment installer Catch-up TV & More — *How-to install Catch-up TV & More*

* **Français**: <https://catch-up-tv-and-more.github.io/fr/installation/>
* **English**: <https://catch-up-tv-and-more.github.io/installation/>

## Chaînes disponibles — *Available channels*

* **Français**: <https://catch-up-tv-and-more.github.io/fr/channels/>
* **English**: <https://catch-up-tv-and-more.github.io/channels/>

## Sites internet disponibles — *Available Websites*

* **Français**: <https://catch-up-tv-and-more.github.io/fr/websites/>
* **English**: <https://catch-up-tv-and-more.github.io/websites/>

## Bugs et améliorations — *Bugs and improvements*
Retours de bugs, propositions d'améliorations ou d'ajout de contenus sont les bienvenus ! GitHub.
⚠️Veuillez tester la dernière version beta avant de soumettre un bug.⚠️

*Bug reports, suggestions for improvements and content additions are welcome! GitHub.*
*⚠️Please try the latest beta version before issuing a bug.⚠️*


## Forums

* **Français**: <https://forum.mpdb.tv/index.php/topic,35713.0.html>
* **English**: <https://forum.kodi.tv/showthread.php?tid=307107>
