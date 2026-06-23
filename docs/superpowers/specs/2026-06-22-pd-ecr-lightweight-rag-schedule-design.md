# PD-ECR Lightweight RAG And Signature Schedule Design

## Goal

Allow users to enter only change source, change reason, change description, and
optional target close date, then use RAG to generate the remaining PD-ECR draft
content and show deterministic first/second signature date suggestions.

## Design

The backend `NewPdEcrRequest` keeps the existing full V1 fields but treats
identity fields such as DC No, MCR No, product number, part number, customer
project, and change type as optional context. The three lightweight RAG signals
are normalized as `change_source`, `change_reason`, and `change_description`.
Legacy aliases continue to work: `source -> change_source`,
`reason -> change_reason`, and `change_proposal -> change_description`.

Retrieval builds its keyword/metadata signal from the three lightweight fields
first, then uses any supplied metadata as ranking boosts. Generation receives
the same normalized request and marks modules needing unavailable formal data as
`needs_human_input` instead of inventing missing product or approval details.

Scheduling is a pure rule helper:

- `second_signature_date = target_close_date - 5 business days`
- `first_signature_date = target_close_date - 10 business days`

Weekends are skipped. Public holidays are not included in V1.

## UI

The new PD-ECR workflow requires only change source, reason, and description for
search/generation. Target close date remains optional. When it is present, the
form shows first and second signature suggestions in the initial input step.

## Testing

Backend tests cover lightweight input normalization and business-day date
calculation. Frontend Playwright covers the visible date suggestions and the
reduced required-field flow.
