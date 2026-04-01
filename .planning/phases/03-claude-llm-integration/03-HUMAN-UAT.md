---
status: partial
phase: 03-claude-llm-integration
source: [03-VERIFICATION.md]
started: 2026-04-01T00:00:00Z
updated: 2026-04-01T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Commande complexe vers Claude
expected: Envoyer "mets l'ambiance pour regarder un film" → Claude répond en français avec une action (ex: scène lumière) ou une demande de clarification — pas "Je n'ai pas compris la commande."
result: [pending]

### 2. Payload filtrage DEBUG
expected: Inspecter les logs HA en mode debug → confirmer que seules les entités des domaines autorisés avec exactement 3 champs (entity_id, friendly_name, state) sont envoyées à l'API Claude
result: [pending]

### 3. Fallback gracieux sur erreur 401
expected: Configurer une clé API invalide → envoyer une commande ambiguë → le message français "Clé API Claude invalide. Vérifiez la configuration." apparaît dans l'interface, sans stack trace visible
result: [pending]

### 4. Absence de données d'habitudes
expected: Inspecter le trafic réseau sortant → confirmer que seules les listes d'entités filtrées sont envoyées (pas de données comportementales ou d'état complet HA)
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
