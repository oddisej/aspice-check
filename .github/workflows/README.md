# GitHub Workflows

## `ci.yml` — Continuous Integration

Runs the full test suite on push to `master`/`main` and on pull requests. Tests run against Python 3.10, 3.11, and 3.12.

## `release.yml` — PyPI Publish + GitHub Release

Builds and publishes packages to PyPI and creates a GitHub release. Each package has its **own version number** in its `pyproject.toml` and releases independently.

### How it decides what to publish

Each publish job reads that package's version from its `pyproject.toml` and checks if that version already exists on PyPI.
- If already published → **skipped** (no error)
- If not yet published → built and uploaded

This means you can bump a subset of packages without breaking the workflow for the others.

### Triggers

**Per-package tag** (recommended for independent releases):
```bash
git tag confluence-ai/v0.3.0
git push origin confluence-ai/v0.3.0
```
This will attempt to publish only `confluence-ai`. Same pattern for `aspice-eval/vX.Y.Z` and `aspice-check/vX.Y.Z`.

**Unified tag** (coordinated releases — all packages at same version):
```bash
git tag v0.2.1
git push origin v0.2.1
```
This considers all three packages; each is published only if its current version isn't already on PyPI.

**Manual dispatch** (via GitHub Actions UI):
- Go to Actions → Release → Run workflow
- Inputs:
  - `packages` — `all` or one of `confluence-ai`, `aspice-eval`, `aspice-check`
  - `test_pypi` — if `true`, publishes to TestPyPI instead of production
- Uses the current version in each package's `pyproject.toml`
- Does NOT create a GitHub release (only tag pushes do)

### GitHub Release

A GitHub release is created for every tag push (both unified and per-package). The release includes:
- Auto-generated release notes from commits since the previous tag
- All built wheels and sdists from the packages that were actually published

TestPyPI uploads skip release creation.

### Required Secrets

Configure in GitHub repo settings → Secrets and variables → Actions:

| Secret | Description |
|---|---|
| `PYPI_API_TOKEN` | PyPI API token (starts with `pypi-...`). Create at https://pypi.org/manage/account/token/ |

### Publish Order

Packages always publish in dependency order when more than one is targeted:
1. `confluence-ai` (standalone)
2. `aspice-eval` (standalone)
3. `aspice-check` (depends on both above)

### Versioning

Each package has its own version in `pyproject.toml` and `__init__.py`. Bump the versions there before tagging. The workflow does not bump versions automatically.
