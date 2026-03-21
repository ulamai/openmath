# Gateway

The local gateway is currently implemented in [`openmath/api/http/server.py`](/Users/blackfrog/Projects/openmath/openmath/api/http/server.py).

Phase 1 serves:

- the browser UI from `apps/web/`
- a local JSON API
- project discovery against the disk-backed `.openmath/` workspace

WebSocket streaming is intentionally deferred until the run/event model is broader than the bootstrap slice.
