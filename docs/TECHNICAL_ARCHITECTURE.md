# Architecture technique

## 1. Principes
Monolithe modulaire, un seul déploiement, domaines séparés par package. Pas de microservices.

## 2. Stack (validée avec réserves)
- Frontend : Next.js + React + TypeScript + Tailwind + shadcn/ui (composants copiés dans le repo, pas de dépendance lourde).
- Backend : FastAPI (Python) + SQLAlchemy 2 + Alembic + Pydantic.
- BDD : PostgreSQL (avec Row-Level Security pour le multi-tenant).
- Tâches longues : file de jobs (Redis + RQ ou arq). Celery est surdimensionné pour le MVP.
- Stockage : S3 compatible, région UE (ex. Scaleway/OVH/Hetzner — à comparer).
- Documents : PyMuPDF, openpyxl, python-docx, Tesseract/OCR local pour commencer.
- IA : couche `ai/providers` (interface unique, implémentations Anthropic/OpenAI), sorties structurées validées par Pydantic.
- Infra : Docker Compose ; un seul VPS au début ; CI GitHub Actions.

**Point de vigilance :** deux langages (TS + Python) pour une petite équipe = coût de contexte. Acceptable car Python est indispensable pour le traitement documentaire/plans ; garder le frontend simple (pas de logique métier côté front, contrats générés depuis OpenAPI).

## 3. Structure du dépôt
```
newton/
  apps/web/            # Next.js
  apps/api/            # FastAPI
    newton/
      core/            # config, sécurité, tenancy, audit
      domains/
        company/ crm/ tenders/ pricing/ catalog/ documents/ ai/ ...
      integrations/    # un package par connecteur, interface commune
      workers/
    migrations/
    tests/
  infra/               # docker-compose, scripts
  docs/
```

## 4. Multi-tenant
Schéma partagé, colonne `company_id` sur toutes les tables métier, **RLS PostgreSQL** activée + filtre applicatif (défense en profondeur). Tests automatisés d'isolation obligatoires (un utilisateur de A ne lit jamais B). Chemins S3 préfixés par `company_id`.

## 5. Moteur de chiffrage
Module Python pur, sans LLM, entièrement testé (décimaux `Decimal`, arrondis documentés). Entrées : lignes, quantités, prix, coefficients (par famille/type de travaux), temps de pose, taux horaires, frais. Sortie : déboursé sec, frais, marge, prix de vente, avec **décomposition par ligne** pour éviter les doubles comptages (main-d'œuvre ≠ frais ≠ marge).

## 6. Pipeline d'analyse documentaire
Upload → classification (type de pièce) → extraction texte par page (PyMuPDF, OCR si besoin) → découpage → extraction IA structurée (prestation, norme, exigence, quantité) → chaque item : `source_document_id`, `page`, `extrait`, `confiance`, `statut` (suggéré/validé/rejeté). Aucune donnée IA n'alimente un chiffrage sans validation humaine.

## 7. Agent IA (couche outils)
Outils nommés, typés, avec permissions : lecture libre selon rôle ; actions sensibles = proposition + confirmation explicite de l'utilisateur ; journal complet (entrée, outil, sortie, utilisateur, validé par).

## 8. Plans (phase 2)
Ordre de difficulté : DXF/PDF vectoriel (faisable) → PDF scanné (incertain) → DWG (licence/connecteur). Voir INTEGRATIONS.md. Toujours niveau de confiance + correction visuelle.

## 9. Budget indicatif (< 100 €/mois) — **estimations à confirmer par devis**
| Poste | Ordre de grandeur |
|---|---|
| VPS UE (8 Go RAM) | 15–40 € |
| Stockage objet + sauvegardes | 5–10 € |
| Domaine, e-mail transactionnel | 2–10 € |
| API LLM (développement + pilote) | 20–40 € (plafond configuré) |
| Monitoring/erreurs (offre gratuite) | 0 |
Risque : l'analyse de gros dossiers (centaines de pages) peut faire exploser le coût LLM → mise en cache, modèle léger pour le tri, modèle plus fort seulement pour l'extraction, quotas par entreprise.
