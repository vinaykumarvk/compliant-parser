# KIS PS-WMS Migration Adapter

## Purpose

The Knowledge Intelligence Service is designed to absorb the reusable patterns from the PS-WMS intelligence service without coupling new domains to PS-WMS concepts. Migration should be explicit and testable.

## Entity Mapping

| PS-WMS | KIS |
| --- | --- |
| `app_id` | `domain_id` |
| `client_id` | domain membership or service principal |
| document | source document |
| document chunk + embedding | document chunk in a vector namespace |
| entity node | graph node |
| entity edge | graph edge |
| extracted fact | extracted fact |
| wiki article | wiki article |
| reasoning chain | reasoning pattern |
| prompt config | prompt template |
| published app corpus | published knowledge snapshot |

## Cutover Gates

- Golden-set hybrid retrieval parity is measured for each migrated domain.
- Graph node/edge counts and approved fact counts are reconciled.
- Wiki article citations and broken-link reports are reviewed.
- Active prompt versions are approved and activated in KIS.
- Retrieval and reasoning use the latest published KIS snapshot.
- PS-WMS `app_id` access controls are mapped to KIS domain memberships before traffic moves.

## Adapter Contract

Legacy callers should provide `app_id`, `client_id`, query text, and optional prompt/pattern name. The adapter resolves:

- `app_id` to `domain_id`
- active corpus to `knowledge_base_id` and latest published snapshot
- PS-WMS prompt identifiers to KIS prompt templates and reasoning patterns

The adapter must not copy plaintext provider credentials. Domain admins re-register provider configs and encrypted credentials in KIS.
