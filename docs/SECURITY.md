# Sécurité et conformité

## Exigences techniques
- Mots de passe : Argon2id ; MFA (TOTP) prévu ; sessions courtes + refresh, révocation.
- Isolation : RLS PostgreSQL + tests d'isolation en CI ; clés S3 préfixées par tenant.
- Secrets : variables d'environnement/gestionnaire de secrets, jamais dans le dépôt ; scan de secrets en CI.
- Chiffrement : TLS partout, chiffrement au repos (disque/objet) ; champs sensibles (RH, IBAN) chiffrés applicativement.
- Sauvegardes : quotidiennes chiffrées, **test de restauration** périodique.
- Journalisation : audit des modifications et des actions IA.
- Fichiers uploadés : validation de type, antivirus (ClamAV) [À VÉRIFIER charge sur VPS], taille limitée.

## IA et données
- Fournisseurs LLM : vérifier DPA, localisation, politique de non-entraînement ; informer les clients (sous-traitants RGPD).
- Injection de prompt : le contenu des documents est traité comme donnée non fiable ; les outils de l'agent sont limités, typés, avec confirmation humaine pour toute action sensible.

## RGPD
Registre des traitements, DPA clients, export/suppression par tenant, durées de conservation (obligations comptables à confirmer avec un juriste/expert-comptable), droits d'accès. Données RH : permissions strictes, minimisation.

## Réglementaire
Facturation électronique, conservation des factures, responsabilité des notes de calcul : **validation par un juriste et un bureau d'études qualifié** avant toute promesse commerciale.
