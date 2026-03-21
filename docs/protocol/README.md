# Protocol Notes

Phase 1 currently exposes JSON endpoints over HTTP:

- `GET /api/projects`
- `GET /api/projects/:id/state`
- `GET /api/projects/:id/runs`
- `GET /api/projects/:id/graph`
- `GET /api/projects/:id/backends`
- `GET /api/doctor`

WebSocket events are specified in the README but not implemented yet.
