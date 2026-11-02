# Compte rendu — sous-phase 1a (socle technique)

Date : 2026-11-02 · Branche : `phase-1a`

## Fonctionnalités livrées
- Dépôt structuré en monolithe modulaire (`apps/api`, `apps/web`, `infra`, `docs`).
- Docker Compose : PostgreSQL 16, job de migration, API FastAPI, site Next.js 16 ; services outils `admin` et `test`.
- Authentification : e-mail + mot de passe (Argon2id), jeton d'accès 15 min + renouvellement 7 jours en cookies httpOnly/SameSite=Strict, rotation du jeton de renouvellement avec détection de réutilisation, déconnexion, révocation par l'admin, mot de passe provisoire à changer, limitation des tentatives, protection CSRF.
- Entreprises et utilisateurs : 3 rôles (admin, chargé d'affaires, lecture), un utilisateur peut appartenir à plusieurs entreprises (changement d'entreprise), protection du dernier administrateur, désactivation avec coupure immédiate.
- Isolation multi-tenant : RLS PostgreSQL (ENABLE + FORCE) sur toutes les tables + filtre applicatif ; l'API utilise un rôle restreint `newton_app` (pas de BYPASSRLS, propriétaire de rien, ni DELETE ni TRUNCATE).
- Journal d'audit en ajout seul (refus des UPDATE/DELETE en base, même pour le propriétaire), écrit dans la même transaction que la modification, champ acteur `user | ai | system`.
- Données de démonstration séparées (`seed-demo`, entreprises `is_demo`, bandeau « DÉMO » dans l'interface, refusé en production).
- Interface web : connexion, changement de mot de passe, accueil (fiche entreprise), utilisateurs, journal d'audit.
- Intégration continue GitHub Actions : tests API sur PostgreSQL, ruff, lint/typecheck/build web, audit npm, scan de secrets gitleaks.

## Tests réellement exécutés
- `docker compose --profile tools run --rm test` : **72 réussis, 0 échec** (1 avertissement de dépréciation d'une bibliothèque de test).
- Test de sabotage : RLS retirée d'une table → 5 tests échouent comme prévu, puis fichier restauré.
- `ruff check` + `ruff format --check` : OK.
- Web, dans Docker (Node 22) : `eslint` 0 erreur, `tsc --noEmit` OK ; `next build` OK (via `docker compose up --build`).
- `npm audit --omit=dev` : 0 vulnérabilité.
- Parcours de bout en bout via le site (port 3000) avec 2 entreprises de démo : connexion, mot de passe provisoire, ajout d'utilisateur, tentatives inter-entreprises refusées, rôles, journal, renouvellement, déconnexion.

## Non vérifié / limites connues
- Le pipeline GitHub Actions n'a pas tourné sur GitHub (dépôt non relié).
- L'interface n'a pas été testée visuellement dans un navigateur, ni par tests automatisés d'interface.
- Limitation des tentatives de connexion en mémoire : à déplacer dans un stockage partagé si plusieurs serveurs.
- MFA (TOTP), réinitialisation de mot de passe par e-mail : non faits.
- 16 alertes « modérées » npm dans les outils de développement (ESLint), non livrées en production.
