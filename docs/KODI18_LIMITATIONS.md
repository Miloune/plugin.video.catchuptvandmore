# Limites de lecture Kodi 18 / InputStream Adaptive 2.4.8

À consulter dès qu'un **merge amont introduit un resolver avec DRM**, ou qu'une
chaîne « ne marche pas » alors que le resolver retourne bien une URL.

## Règle ISA 2.4.8

| Type de flux | Lisible sur cette cible ? | Pourquoi |
| --- | --- | --- |
| HLS clair (aucun `EXT-X-KEY`) | oui | lecture directe |
| DASH + Widevine CENC (`.mpd`) | oui | 6play, replay RMC+ |
| HLS `EXT-X-KEY:METHOD=SAMPLE-AES` | **non** | le parseur rejette le manifeste (`ENCRYPTIONTYPE_INVALID`) ; le déchiffreur ne gère que `cenc` |

Les manifestes multi-DRM (FairPlay + PlayReady + Widevine) sont rejetés dès la
première clé `SAMPLE-AES` non-Widevine — donc même un flux contenant du
Widevine ne passe pas si le manifeste liste aussi FairPlay/PlayReady.

Preuves dans la source `inputstream.adaptive`, tag `2.4.8-Leia` :

- `src/parser/HLSTree.cpp`, `processEncryption()` : `METHOD=SAMPLE-AES` →
  `ENCRYPTIONTYPE_INVALID` avec le log `Unsupported encryption method: SAMPLE-AES`.
- `wvdecrypter.cpp` : `cdm::EncryptionScheme::kCenc` codé en dur (pas de `cbcs`).

Symptômes dans `kodi.log` :

```
ERROR: AddOnLog: InputStream Adaptive: Unsupported encryption method: SAMPLE-AES
ERROR: AddOnLog: InputStream Adaptive: Could not open / parse mpdURL (<url>.m3u8)
```

## Cas connus (version 0.2.43~beta04)

- **RMC+** (`resources/lib/channels/fr/rmcplus.py`) : directs `RMC Story`,
  `RMC Découverte`, `RMC Life` en HLS SAMPLE-AES → illisibles ; garde-fou
  notification (`#30897`) dans `get_live_url` (direct DRM en HLS uniquement).
- RMC+ direct `TECH`, `BFM TV`, `BFM2` : flux clairs → OK (inchangés).
- RMC+ replay : DASH/CENC → OK.
- BFM TV/Business/BFM2/régions via `bfmtv.py` (pages `bfmtv.com/*/en-direct/`) :
  HLS clair → OK.
- 6play replay : DASH/CENC + patch `preferred_video_codec=h264` (Amlogic).

## Réflexe lors d'un merge

1. Repérer les resolvers qui appellent
   `resolver_proxy.get_stream_with_quality(..., license_url=...)` avec un
   `manifest_type='hls'`.
2. Vérifier le manifeste (`curl` + `grep EXT-X-KEY`) :
   - `SAMPLE-AES` → illisible sur Kodi 18. Chercher une source officielle
     claire ou DASH sur le site du diffuseur ; sinon ajouter un garde-fou
     (modèle : `rmcplus.get_live_url` → `plugin.notify(...)` +
     `return False`, avec une chaîne localisée dédiée).
   - DASH/CENC ou clair → rien à faire.
3. Vérifier le comportement réel sur l'appareil
   (`tools/device_compile_test.sh` pour la syntaxe, `kodi.log` pour la lecture).
