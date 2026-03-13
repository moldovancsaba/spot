# {spot} Operational Notes

## Important Truths

- Apertus on MLX is the intended primary classifier route.
- Historical artifacts proved MLX classifier runs existed before docs caught up.
- Older artifacts may still show `model_version` as `ollama:qwen2.5:7b`; this was a reporting defect, not the real runtime route.

## Known Operational Risks

- MLX requires locally available model weights and `mlx_lm` runtime.
- If MLX route fails, {spot} falls back deterministically and flags the event.
- Evaluation with mixed runtimes requires explicit `backend://model` specs.
- The repo directory in this workspace is not a Git repository, so Git-based provenance inside this folder is unavailable.
