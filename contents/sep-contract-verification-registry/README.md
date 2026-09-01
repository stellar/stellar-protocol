# Contract Verification Registry API — schemas and examples

Supporting files for the Contract Verification Registry API SEP
(`ecosystem/sep-contract-verification-registry.md`). They let implementers
validate responses against a machine-readable schema and use the documented
examples as test fixtures.

## Layout

- `status-object-1.0.schema.json` — JSON Schema (draft 2020-12) for the body of a
  `200 OK` or `202 Accepted` response from `GET /wasms/:wasm_hash.json`.
- `error-1.0.schema.json` — JSON Schema for the body a `400 Bad Request` MAY carry.
  Other non-2xx statuses are signaled by status code and define no body.
- `examples/status/` — example status objects, named by HTTP status and
  scenario. Each validates against `status-object-1.0.schema.json`.
- `examples/error/` — example `400` error bodies, named `<error-code>.json`.
  Each validates against `error-1.0.schema.json`.

The example files are the exact JSON snippets embedded in the SEP, extracted so
they can be validated (e.g. in CI).

## Validating

Any draft 2020-12 validator works. The schemas declare their draft via
`$schema`, so a validator that respects it needs no extra flags.

Using
[`check-jsonschema`](https://github.com/python-jsonschema/check-jsonschema)
(`pipx install check-jsonschema`):

```
# Status objects
check-jsonschema --schemafile status-object-1.0.schema.json examples/status/*.json

# Error bodies
check-jsonschema --schemafile error-1.0.schema.json examples/error/*.json
```
