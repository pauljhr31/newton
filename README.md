# NEWTON

ERP SaaS multi-entreprises pour TPE/PME d'électricité (5 à 20 salariés en cible). Nom provisoire.

**Statut : sous-phase 1a terminée (socle technique).** Prochaine étape : 1b (documents, DPGF Excel, moteur de chiffrage).

## Démarrer en local (Windows + Docker Desktop)

Prérequis : Docker Desktop démarré, Python 3.12 (uniquement pour créer le fichier `.env`).

```powershell
cd C:\dev\newton
python infra/scripts/make_env.py      # une seule fois : crée .env avec des secrets aléatoires
docker compose up -d --build          # démarre base de données, API et site web
```

Ouvrir http://localhost:3000.

### Créer une entreprise réelle et son administrateur
```powershell
docker compose --profile tools run --rm admin create-company --name "Ma Société" --admin-email moi@exemple.fr --admin-name "Prénom Nom"
```
Le mot de passe provisoire s'affiche une seule fois ; il devra être changé à la première connexion.

### Données de démonstration (séparées, marquées « DÉMO »)
```powershell
docker compose --profile tools run --rm admin seed-demo                  # crée 2 entreprises fictives
docker compose --profile tools run --rm admin seed-demo --reset-passwords # nouveaux mots de passe provisoires
```
Refusé si `NEWTON_ENV=production`.

### Lancer les tests
```powershell
docker compose --profile tools run --rm test
```
Les tests utilisent une base séparée (`newton_test`), recréée à chaque lancement.

### Arrêter
```powershell
docker compose down        # arrête (les données sont conservées)
```

## Structure
```
apps/api/      FastAPI (Python) : newton/core (config, sécurité, tenancy, audit), newton/domains/*
  migrations/  Alembic (schéma + règles RLS)
  tests/       pytest, sur un vrai PostgreSQL
apps/web/      Next.js (TypeScript, Tailwind)
infra/         scripts
docs/          conception
.github/       intégration continue
```

## Documents
- [Spécification produit](docs/PRODUCT_SPEC.md)
- [Architecture technique](docs/TECHNICAL_ARCHITECTURE.md)
- [Schéma de base de données](docs/DATABASE_SCHEMA.md)
- [Intégrations](docs/INTEGRATIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [Sécurité et conformité](docs/SECURITY.md)
- [Décisions et questions ouvertes](docs/DECISIONS.md)
- [Compte rendu 1a](docs/PHASE_1A_REPORT.md)

## Convention
Tout ce qui est marqué **[À VÉRIFIER]** n'a pas été confirmé et ne doit pas être traité comme acquis.
