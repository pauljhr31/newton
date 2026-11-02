# Spécification produit — NEWTON

## 1. Positionnement
Couche intelligente de chiffrage et de pilotage pour TPE/PME d'électricité, qui cohabite avec les outils existants (Excel, Word, Batigest, AutoCAD). Elle ne les remplace pas dans un premier temps.

## 2. Coin d'entrée recommandé (wedge)
**Le chiffrage d'appels d'offres** (CCTP + DPGF Excel). C'est la douleur la plus coûteuse en temps pour un chargé d'affaires, la plus différenciante, et la moins dépendante d'intégrations tierces. Les modules CRM/facturation/compta sont des domaines saturés (Batigest, Obat, Henrri…) : ne pas les attaquer en premier.

## 3. Personas
| Persona | Besoin principal |
|---|---|
| Dirigeant | Savoir si une affaire est rentable avant de répondre |
| Chargé d'affaires / d'études | Chiffrer vite un DPGF, tracer ses hypothèses |
| Conducteur de travaux (phase 4) | Budget vs réel du chantier |
| Technicien (phase 4) | Saisie d'heures / photos sur mobile |

## 4. MVP recommandé (plus étroit que le « Phase 1 » du prompt initial)
Objectif : une entreprise réelle chiffre un vrai DPGF de bout en bout.

Inclus :
1. Authentification, entreprise (tenant), utilisateurs, 3 rôles (Admin, Chargé d'affaires, Lecture).
2. Clients et fournisseurs (fiches simples).
3. « Affaire / consultation » : conteneur de documents, statut, notes.
4. Import documentaire (PDF, Excel, Word) avec stockage et classification.
5. Analyse CCTP assistée par IA : prestations, normes citées, exigences — **chaque extraction citée avec document + page**, statut « à valider ».
6. Lecture DPGF Excel : détection des colonnes/lignes, structure conservée, copie de travail (original jamais modifié).
7. Moteur de chiffrage déterministe : prix d'achat, coefficients par famille, main-d'œuvre (temps de pose × taux), frais généraux, marge ; déboursé sec séparé.
8. Bibliothèque de prix/ouvrages importable (CSV/Excel) avec historique de prix.
9. Quantitatif saisi/corrigé par l'utilisateur, avec suggestions IA depuis le CCTP (niveau de confiance affiché).
10. Export : DPGF Excel complété, rapport de contrôle (lignes non chiffrées, hypothèses), déboursé sec.
11. Journal d'audit (dont actions IA).

Exclus du MVP (volontairement) : lecture automatique de plans/DWG, intégrations (Batigest, Rexel, Ecodial, banque), devis/factures complets, achats/stocks, RH, mobile, secrétaire IA conversationnelle à actions, mémoire technique généré.

## 5. Critères de succès du MVP
- Un DPGF réel de 100–500 lignes est rempli en moins de ~1 h au lieu d'une demi-journée+ (à mesurer avec un pilote).
- 100 % des valeurs extraites par IA sont traçables à une source.
- Aucun prix « inventé » : tout prix vient de la bibliothèque, d'une saisie ou d'un coefficient, jamais d'un LLM.

## 6. Modules du prompt initial — priorisation
| Module | Phase | Remarque |
|---|---|---|
| 4 Chiffrage / AO | MVP | Cœur du produit |
| 1 Entreprise, 5 Produits (base) | MVP | Version minimale |
| 2 CRM | MVP minimal, puis P4 | Fiches seulement |
| 3 Devis/Facturation | P4+ | Facturation électronique = chantier réglementaire lourd ; envisager de déléguer à une PA agréée |
| 6 Bureau d'études | P3+ | Très coûteux, forte responsabilité |
| 7 Chantiers, 8 Achats/Stocks, 10 Personnel | P4 | Après validation du chiffrage |
| 9 Finance/Compta | P4+ | Rester complémentaire d'un logiciel comptable |
| 11 Secrétaire IA | MVP léger (lecture), actions en P4 | Outils contrôlés + confirmations |
