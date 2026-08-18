# Manual hardware scripts

Scripts here require a physical Wooting keyboard and are **not** collected by
pytest or run in CI — pytest's default discovery only picks up `test_*.py`
directly under `tests/`, and these live in `tests/manual/` with a `manual_`
prefix specifically to stay out of that.

Run one directly, e.g.:

```bash
python tests/manual/manual_none_duration.py
```
