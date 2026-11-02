# Schéma de base de données (MVP + extensions prévues)

Conventions : UUID, `company_id` sur toutes les tables métier, `created_at/updated_at/created_by`, suppression logique pour les données comptables.

## Cœur
- `companies` (id, name, siret, settings jsonb, ...)
- `users` (id, email, password_hash, ...) ; `memberships` (user_id, company_id, role)
- `audit_log` (company_id, user_id|ai, action, entity, before/after jsonb, ts)

## CRM minimal
- `parties` (company_id, kind: client|prospect|supplier, name, siret, ...) ; `contacts`

## Documents
- `documents` (company_id, tender_id?, filename, mime, storage_key, sha256, doc_type: CCTP|DPGF|BPU|DQE|CCAP|PLAN|AUTRE, status)
- `document_pages` (document_id, page_no, text, ocr bool)

## Consultations / chiffrage
- `tenders` (company_id, party_id, reference, title, status, due_date)
- `extractions` (tender_id, document_id, page, kind: prestation|norme|exigence|quantite, payload jsonb, quote, confidence, status)
- `boq_sheets` (tender_id, source_document_id, working_copy_key, column_mapping jsonb)
- `boq_lines` (boq_sheet_id, row_ref, code, label, unit, qty, qty_source, price_item_id?, unit_cost, labour_minutes, unit_price, status)
- `pricing_profiles` (company_id, name, hourly_rate, overhead_pct, margin_pct, ...)
- `pricing_coefficients` (profile_id, family_id|work_type, kind, value)

## Catalogue
- `product_families`, `products` (manufacturer, supplier_id, reference, label, specs jsonb, ...)
- `price_history` (product_id, buy_price, sell_price, valid_from, source)
- `ouvrages` (+ `ouvrage_components`) pour les compositions

## Prévus (phases 4+)
`projects`, `project_budgets`, `time_entries`, `purchase_orders`, `stock_movements`, `invoices` (numérotation séquentielle sans trou, verrouillage), `employees`, `ai_actions`, `integration_connections`, `sync_runs`.

## Règles
- Montants : `NUMERIC(14,4)`, jamais float.
- Factures émises : immuables (avoir pour corriger).
- Données de démonstration : flag `is_demo` sur les entreprises, jamais mélangées au réel.
