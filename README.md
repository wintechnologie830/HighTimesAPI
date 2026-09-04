Aronium Loyalty / Points API

Cette API permet de connecter Aronium POS à une application mobile de fidélité.

En termes simples : Aronium continue de gérer les clients et les ventes comme d'habitude. L'API lit ces informations et gère les points de fidélité séparément, sans modifier Aronium.

Comment ça fonctionne
Aronium (pos.db) → Informations sur les clients et les achats. Lecture seule.
Base de données de fidélité (loyalty.db) → Points, historique des points et informations de fidélité.
Application mobile → Communique avec l'API pour afficher et gérer les points des clients.
Aronium → Loyalty API → Application mobile
             ↓
         loyalty.db
Installation

Installez les dépendances nécessaires :

pip install -r requirements.txt

Ensuite, démarrez le serveur FastAPI :

uvicorn app.main:app --reload

L'API sera disponible à :

http://127.0.0.1:8000

Documentation interactive de l'API :

http://127.0.0.1:8000/docs
Configuration

Créez un fichier .env à partir de .env.example et configurez :

ARONIUM_DB_PATH → Emplacement du fichier pos.db d'Aronium
LOYALTY_DB_PATH → Emplacement où loyalty.db doit être enregistré
API_KEY → Clé secrète utilisée pour protéger l'API

Gardez loyalty.db en dehors du dossier Data d'Aronium.

Attribution automatique des points

L'API peut vérifier périodiquement les nouvelles ventes effectuées dans Aronium et attribuer automatiquement les points.

Cette vérification peut être programmée avec le Planificateur de tâches Windows ou un autre système de planification.

Important
La base de données d'Aronium n'est jamais modifiée.
Les données de fidélité sont stockées séparément dans loyalty.db.
Faites régulièrement des sauvegardes de loyalty.db.
Gardez la clé API secrète.