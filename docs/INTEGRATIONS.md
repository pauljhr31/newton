# Intégrations — état de faisabilité

Aucune intégration ci-dessous n'est vérifiée. Statuts : **Réalisable** (standard/ouvert), **À vérifier** (API/licence/accord à confirmer), **Risqué** (dépend d'un tiers fermé).

| Cible | Approche | Statut | Action avant de coder |
|---|---|---|---|
| Excel (.xlsx) | openpyxl, copie de travail | Réalisable | Collecter 5+ DPGF réels (formats variés, cellules fusionnées, macros) |
| Word (.docx) | python-docx / modèles | Réalisable | — |
| PDF | PyMuPDF | Réalisable | — |
| DXF | ezdxf (lecture) | Réalisable | — |
| DWG | Convertisseur local, ou bibliothèque tierce sous licence (ODA) / LibreDWG (licence GPL à analyser), ou plug-in AutoCAD local (.NET) | À vérifier / coût | Alternative MVP+ : demander DXF/PDF export au client |
| AutoCAD (pilotage) | Connecteur local Windows (AutoLISP/.NET/COM) | À vérifier | Nécessite une licence AutoCAD chez le client, agent installé sur son poste |
| AutoCAD Electrical | API propre | À vérifier | Dépend de l'édition |
| Sage Batigest Connect | Aucune API publique confirmée de mon côté | À vérifier | Contacter Sage / partenaire, demander doc et conditions ; repli : import/export CSV/Excel |
| Ecodial (Schneider) | Pas d'API ouverte connue | À vérifier / Risqué | Repli : import/export de fichiers, résultats lus en PDF/Excel |
| Caneco BT | Idem | À vérifier / Risqué | Idem |
| Rexel / Sonepar / CGED / YESSS | Catalogues/exports/EDI réservés aux comptes clients | À vérifier | Demander l'accès via le compte pro du pilote ; **pas de scraping** |
| Pennylane / compta | API existante côté éditeur | À vérifier | Lire la doc officielle et les conditions partenaires |
| Banque | Agrégateur agréé (DSP2) ou import CAMT/OFX/CSV | À vérifier / coût | MVP : import de fichiers uniquement |
| Facturation électronique | Plateforme agréée (PA) tierce via API | À vérifier (calendrier réglementaire) | Ne pas devenir PA ; s'intégrer à une PA |

## Contrat commun d'un connecteur
`connect()`, `test()`, `pull(since)`, `push(items)`, `status()` ; journal de synchronisation ; reprise sur erreur ; permissions ; documentation dédiée. **Source de vérité** par type de donnée à définir par intégration (ex. : factures → logiciel de facturation existant ; prix → NEWTON).
