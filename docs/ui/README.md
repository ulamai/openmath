# UI Notes

The initial UI is a single static shell served by the gateway. It now uses a
four-pane workspace shape:

- project picker
- per-project thread list
- main conversation or research view
- context inspector

This shifts the product closer to the OpenClaw / LM Studio interaction model while
keeping OpenMath’s research state on disk under `.openmath/`.
