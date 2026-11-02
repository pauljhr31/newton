# Décisions et questions ouvertes

## Décisions d'architecture proposées (ADR)
| # | Décision | Statut |
|---|---|---|
| 1 | Monolithe modulaire | **Acceptée** (2026-11-02) |
| 2 | Multi-tenant schéma partagé + RLS | **Acceptée**, implémentée en 1a |
| 3 | Le chiffrage est déterministe ; l'IA suggère, l'humain valide | **Acceptée** |
| 4 | Produit complet construit par tranches ordonnées, chiffrage d'AO (CCTP + DPGF) en premier | **Décidée par le fondateur** (2026-11-02) |
| 5 | Plans : DXF/PDF vectoriel avant DWG | Proposée |
| 6 | Intégrations : une par une, après vérification des interfaces | Proposée |
| 7 | Ne pas devenir plateforme agréée de facturation | Proposée |

## Décisions prises en 1a
| # | Décision |
|---|---|
| 8 | Pas d'inscription publique : entreprise + 1er admin créés par commande ; l'admin ajoute ses collègues |
| 9 | Ajout d'un collègue avec mot de passe provisoire (pas d'envoi d'e-mail tant qu'aucun service n'est branché) |
| 10 | Sessions : jeton d'accès 15 min + renouvellement 7 jours en cookies httpOnly, rotation et détection de réutilisation |
| 11 | Next.js 16 (et non 15) : Next 15 embarque une version de PostCSS avec failles connues |

## Décisions bloquantes (besoin du fondateur)
1. Valides-tu le MVP resserré (chiffrage d'AO) plutôt que le MVP large du prompt ?
2. As-tu 1 à 3 entreprises pilotes et des **DPGF/CCTP réels** (anonymisés) pour tester ?
3. Qui développe, et dans quel dépôt/environnement dois-je travailler (repo local, Claude Code, autre) ?
4. Fournisseur d'hébergement UE préféré ? Fournisseur LLM par défaut ?
5. Version/licence Sage Batigest des pilotes ? Contact Sage possible ?
6. Nom « NEWTON » : vérifier disponibilité (INPI, domaine) avant d'investir.
7. Modèle tarifaire visé (abonnement par entreprise/utilisateur) pour calibrer le budget IA.

## Risques majeurs
1. Diversité des DPGF Excel (formats irréguliers) — fort.
2. Fiabilité de la lecture de plans — très fort, reporté en phase 2.
3. Accès aux API tiers/licences — fort.
4. Coût et confidentialité LLM — moyen, maîtrisable par quotas.
5. Responsabilité sur les études électriques — fort, mitigé par validation humaine.
6. Périmètre — très fort, mitigé par le phasage.
