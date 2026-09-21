# High Times — Loyalty App

Trois composants, avec la même architecture qu'auparavant (voir les docstrings de chaque service pour le raisonnement complet) :

```text
loyalty-app (browser)
        │  (X-API-Key: FIDELITY_API_KEY)
        ▼
   fidelity_api  ──────────────►  general_api  ────►  pos.db (Aronium)
        │        (X-API-Key: GENERAL_API_KEY)
        ▼
   loyalty.db (points, comptes, transactions, identifiants de connexion)
```

* **general_api** est le seul service qui ouvre `pos.db`. Il fonctionne en lecture seule pour tout, à l'exception de trois écritures atomiques et limitées : retirer/remettre du stock (`/products/{id}/reduce-stock`, `/increase-stock`), enregistrer une vraie vente (`POST /sales` — `Document` + `DocumentItem` + `Payment`, dans la même transaction que la réduction du stock), et créer un client lors de l'inscription (`POST /customers`). Il doit rester lié à `127.0.0.1`.

* **fidelity_api** est le seul service auquel le navigateur communique directement. Il n'accède jamais au chemin de `pos.db`. Nouveauté dans cette version : `/auth/register` et `/auth/login`, qui utilisent une table `CustomerCredential` située uniquement dans `loyalty.db` — la table `Customer` d'Aronium ne possède aucune colonne de mot de passe et n'en aura jamais.

  L'achat d'un produit utilise maintenant l'endpoint `/sales` de **general_api`. Ainsi, un achat apparaît dans l'écran Sales d'Aronium et est pris en compte dans les statistiques de « popular products », plutôt que d'être enregistré uniquement du côté de la fidélité.

  Nouveauté également : une connexion individuelle pour les employés (`StaffCredential` / `/staff/auth/login`), complètement séparée des comptes clients et d'Aronium — voir la section « Staff accounts » ci-dessous.

* **loyalty-app** est un unique fichier statique `index.html` — aucune étape de build. L'utilisateur s'inscrit ou se connecte, puis peut acheter des produits (ce qui rapporte des points et constitue une vraie vente dans Aronium) ou échanger ses points contre des produits. Chaque carte de produit affiche le stock actuel provenant directement d'Aronium.

## Exécution

### 1. general_api (sur la machine qui exécute Aronium)

```bash
cd general_api
cp .env.example .env   # définir ARONIUM_DB_PATH vers votre pos.db et choisir un GENERAL_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### 2. fidelity_api (sur la même machine ou une autre machine du réseau local)

```bash
cd fidelity_api
cp .env.example .env   # GENERAL_API_KEY doit correspondre à celui de general_api; choisir un FIDELITY_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. loyalty-app

Il suffit d'ouvrir `loyalty-app/index.html` dans un navigateur (ou de le servir depuis n'importe quel emplacement).

Le fichier doit uniquement pouvoir communiquer avec **fidelity_api** via HTTP ; le CORS est déjà ouvert sur l'API.

Dans les « connection settings », définir l'URL de base de **fidelity_api** ainsi que son `X-API-Key`, puis s'inscrire ou se connecter.

### 4. Staff accounts

Les employés créent leur propre compte directement depuis le pickup desk panel, dans un onglet « Create account » situé à côté de « Sign in ».

Aucun enregistrement Aronium n'est créé et aucun lien n'existe avec les comptes clients. Seuls un username, un nom et un password sont stockés dans `loyalty.db`.

Si vous préférez créer les comptes vous-même, `manage_staff.py` fonctionne toujours de la même manière :

```bash
cd fidelity_api

# si vous mettez à niveau un loyalty.db existant, exécuter ceci une seule fois :
python migrate_staff_login.py

python manage_staff.py add jdoe "Jane Doe"     # demande un mot de passe
python manage_staff.py list
python manage_staff.py deactivate jdoe         # désactive le compte sans le supprimer
python manage_staff.py reset-password jdoe
```

Au pickup desk, les employés doivent toujours entrer le « Staff PIN » partagé pour accéder au panel. Ils doivent ensuite se connecter ou créer leur compte individuellement avant que l'action « Mark picked up » puisse être utilisée.

Cela permet d'enregistrer **quel employé** a remis l'article au client, plutôt que de savoir uniquement que le PIN partagé était connu.

Les clients voient uniquement un **id** de staff sur leur écran « My pickups » ; le nom réel de l'employé est affiché uniquement sur le staff pickup desk.

### 5. Migrer les clients Aronium existants

Si le magasin utilise déjà Aronium, ses clients existent dans `pos.db` mais n'ont ni compte de fidélité ni identifiants de connexion. Un script unique les importe (general_api doit être démarré) :

```bash
cd fidelity_api
python migrate_aronium_customers.py run --dry-run              # aperçu, n'écrit rien
python migrate_aronium_customers.py run --csv codes.csv        # migration réelle
python migrate_aronium_customers.py reissue 42 --csv code.csv  # nouveau code pour le client #42
```

Ce que fait la migration, pour chaque client Aronium actif (le « Walk-in customer », les clients désactivés et les clients déjà inscrits dans l'app sont ignorés) :

* Elle crée son compte de fidélité avec **0 point** et aucune transaction : ses achats passés ne sont **pas** compensés. Pour que cela tienne aussi côté synchronisation, le curseur de `/sync` démarre maintenant au dernier document Aronium (et non à 0) sur une nouvelle installation ; seules les ventes faites à partir de ce moment rapportent des points.
* Elle génère un **code d'activation** à usage unique (écrit dans le fichier CSV ; seul son hash est conservé, donc il ne peut pas être récupéré — utiliser `reissue` en cas de perte). Aronium ne stocke aucun mot de passe : le client active son compte avec `POST /auth/claim` (`claim_code`, `password`, et `username` au besoin) et choisit lui-même son mot de passe.
* Elle est **idempotente** : la relancer ne migre que les nouveaux clients.

**Conflits de username :** si le nom Aronium d'un client est déjà utilisé par un compte de l'app, partagé avec un autre client Aronium (sans tenir compte des majuscules), ou vide, le client est signalé dans le rapport (colonne `username_conflict` du CSV), et `/auth/claim` répond **409** en lui demandant de choisir un autre `username`. Celui qui possède déjà le nom le garde. Le nom dans Aronium n'est jamais modifié.

## Nouveautés depuis la dernière version

* Inscription / connexion des clients, avec `/auth/register` et `/auth/login`.
* Comptes individuels pour les employés (`/staff/auth/register`, `/staff/auth/login`), en plus du Staff PIN partagé existant — voir « Staff accounts » ci-dessus. Chaque redemption complétée enregistre maintenant l'employé qui l'a effectuée.
* « My pickups » et le staff pickup desk affichent maintenant l'heure exacte (`HH:MM:SS`) avec la date, plutôt que la date uniquement.
* Affichage du stock en temps réel sur chaque carte de produit.
* L'achat d'un produit (et pas uniquement son redemption avec des points) retire maintenant réellement le stock d'Aronium et crée un véritable document de vente dans Aronium. Il apparaît donc dans les rapports Aronium de la même manière qu'une vente effectuée directement à la caisse.

## Compromis connus à revoir avant une utilisation en production

* `record_sale()` utilise toujours `UserId=1` et `WarehouseId=1` comme identité fixe pour le « web kiosk ». Cela convient à une configuration avec une seule caisse et un seul entrepôt, mais devrait être revu pour une configuration plus complexe.

* Si cette application fonctionne en parallèle avec une vraie caisse qui enregistre également la même transaction, la vente sera comptabilisée deux fois. Il faut donc déterminer quel système constitue la **source of truth** pour chaque achat.

* La connexion client ne possède actuellement aucun session token ni expiration. Après une connexion réussie, le navigateur conserve simplement l'identifiant du client. Cela convient à une application de type kiosk utilisée par un seul utilisateur, mais cette approche n'est pas destinée à une application exposée directement sur Internet.

* Les tokens de connexion des employés (`StaffSession`) n'expirent pas automatiquement non plus. La déconnexion est manuelle via le lien « sign out » du pickup desk, ou le compte peut être désactivé avec `manage_staff.py` si un appareil est perdu.
