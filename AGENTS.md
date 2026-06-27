# Repository Guidelines

## Start Here
Read `readme.md` before changing anything, and keep it in context while you work — it is the source of truth for djultra, a reusable Django extension layer: project scaffolding, admin automation, model/field helpers, DRF serializers, middleware, settings injection + `ConfigLoader`, and the `dev`/fastmanage development workflow. The package source lives under `src/` (imported as the `djultra` package).

If you catch yourself grepping the source to answer "does djultra already have an X?", the answer is almost certainly in `readme.md` — read it first. If it genuinely isn't there, that's a docs gap: add it, so the next reader never has to grep.

## Conventions
djultra preserves the package structure it was extracted from: a module lives in its sub-package (`djultra/services/email.py`, `djultra/models/base.py`), never flattened. Call functions through their module path, not the bare name — it shows where the function lives and how the code is organized:

```python
from djultra import services
services.email.send_templated_email(subject=..., template_name=..., context=..., recipient_list=...)
# not: from djultra.services.email import send_templated_email; send_templated_email(...)
```

## Development
- `python manage.py dev` (in a consuming project) — the improved dev server: autoreload like `runserver`, plus the `django-tasks` worker and the fastmanage daemon as named child processes that shut down with it.
- Fastmanage speeds repeated `manage.py` / `django-admin` calls; it is opt-in per project (import the patch) and falls back to plain Django when its socket is absent.
- Settings: a project loads `djultra.settings` via ultraimport; values resolve through `ConfigLoader` (existing assignment → env var → `CONFIG_FILE` INI `[DEFAULT]` → typed default). Defaults target zero-config local dev; production overrides via env/INI.

## Code Style
- Python: 4-space indentation, `snake_case` functions/fields, `PascalCase` models.
- Keep migrations committed with model changes.
- No formatter config ships here — match the surrounding code.
