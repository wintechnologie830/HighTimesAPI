# High Times — Loyalty / Points project (two-API architecture)

Ce projet est maintenant divisé en **deux services séparés**, pour isoler
complètement la base de données d'Aronium (`pos.db`) de tout ce qui parle à
l'application mobile.

```
Application mobile
        │  (X-API-Key: FIDELITY_API_KEY)
        ▼
   fidelityAPI  ──────────────►  generalAPI  ────►  pos.db (Aronium, lecture seule)
        │        (X-API-Key: GENERAL_API_KEY)
        ▼
   loyalty.db (points, comptes, transactions)
```

## Pourquoi deux API plutôt qu'une seule

Le client veut que la base de données reste sécurisée et privée. Avec une
seule API, le service qui répond au téléphone est aussi celui qui a le
chemin d'accès à `pos.db` en mémoire — si ce service est un jour compromis
(clé volée, bug, dépendance vulnérable, etc.), l'attaquant a une voie directe
vers la base d'Aronium.

En séparant en deux :

- **generalAPI** est le seul programme qui ouvre `pos.db`, toujours en
  lecture seule. Il est configuré pour n'écouter que sur `127.0.0.1`
  (localhost) — il n'est **jamais** accessible depuis le Wi-Fi du magasin,
  seulement depuis fidelityAPI qui tourne sur la même machine.
- **fidelityAPI** est le seul programme que le téléphone contacte. Il ne
  connaît même pas le chemin de `pos.db` — ce n'est pas juste une règle
  qu'il respecte, le code n'a littéralement pas cette information. Pour
  tout ce qui touche aux clients, produits ou ventes, il fait une requête
  HTTP à generalAPI avec un secret que le téléphone ne possède jamais.
- Le téléphone ne détient qu'une seule clé (`FIDELITY_API_KEY`), qui ne
  donne accès qu'à fidelityAPI. Même si cette clé fuit, elle n'ouvre aucune
  porte vers Aronium.

C'est le principe de **défense en profondeur** : compromettre le service
exposé au public (fidelityAPI) ne donne pas automatiquement accès à la
donnée la plus sensible (pos.db).

## Points par client

Chaque client Aronium a son propre `LoyaltyAccount` dans `loyalty.db`, lié
par `aronium_customer_id`. Les soldes ne sont jamais partagés ni regroupés
entre clients — le point de vente identifie le client (carte de fidélité,
recherche par nom, etc.) et fidelityAPI ne renvoie/modifie que le solde de
ce client précis.

- **Gagner des points** : `/points/earn` (manuel) ou automatiquement via
  `/sync/run`, qui lit les nouvelles ventes depuis generalAPI.
- **Dépenser des points sur un produit** : `/points/redeem-product` — le
  prix du produit est demandé en direct à generalAPI (jamais copié dans
  loyalty.db), donc si le prix change dans Aronium, il est immédiatement à
  jour côté fidélité.
- **Dépenser un nombre de points brut** (ex. rabais en argent) :
  `/points/redeem`.
- **Correction manuelle** (geste commercial, erreur à corriger) :
  `/points/adjust`.

## Installation

Chaque service a son propre dossier, son propre `requirements.txt` et son
propre `.env`.

### 1. generalAPI (sur la machine où tourne Aronium)

```bash
cd general_api
cp .env.example .env
# éditez .env : ARONIUM_DB_PATH doit pointer vers votre pos.db,
# et choisissez un GENERAL_API_KEY long et aléatoire.
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Vérifiez bien que `--host` reste `127.0.0.1` — c'est ce qui empêche ce
service d'être joignable depuis le Wi-Fi du magasin.

### 2. fidelityAPI (peut tourner sur la même machine ou une autre du réseau local)

```bash
cd fidelity_api
cp .env.example .env
# éditez .env :
#  - GENERAL_API_KEY doit être IDENTIQUE à celui mis dans general_api/.env
#  - GENERAL_API_BASE_URL doit pointer vers generalAPI (http://127.0.0.1:8001
#    si les deux services sont sur la même machine)
#  - choisissez un FIDELITY_API_KEY long et aléatoire, différent du premier
#    (c'est celui-ci que l'app mobile utilisera)
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

L'application mobile ne parle qu'à `fidelityAPI`, sur le port 8000.
Documentation interactive : `http://<adresse-locale>:8000/docs`.

## Important

- `pos.db` n'est **jamais** modifié — seul generalAPI l'ouvre, toujours en
  mode lecture seule (`sqlite ?mode=ro`), et rien d'autre dans le projet
  n'a accès à son chemin.
- Les deux clés (`GENERAL_API_KEY` et `FIDELITY_API_KEY`) doivent être
  différentes et longues/aléatoires. Ne les commitez jamais dans Git —
  gardez-les seulement dans les fichiers `.env` locaux.
- Faites des sauvegardes régulières de `loyalty.db`.
- Si le serveur de fidélité (les deux API) tombe en panne, Aronium continue
  de fonctionner normalement — aucun des deux services n'est dans le chemin
  critique du paiement.
