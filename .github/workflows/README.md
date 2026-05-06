# GitHub Workflows

## `ci.yml` — Continuous Integration

Runs the full test suite on push to `master`/`main` and on pull requests. Tests run against Python 3.10, 3.11, and 3.12.

## `release.yml` — PyPI Publish + GitHub Release

Builds and publishes the three packages to PyPI and creates a GitHub release.

### Triggers

**Tag push** (recommended for production releases):
```bash
git tag v0.2.1
git push origin v0.2.1
```
This will:
1. Run tests
2. Publish `confluence-ai`, `aspice-eval`, `aspice-check` to PyPI in dependency order
3. Create a GitHub release tagged `v0.2.1` with built wheels/sdists attached

**Manual dispatch** (via GitHub Actions UI):
- Go to Actions → Release → Run workflow
- Inputs:
  - `version` — version string (e.g. `0.2.1`)
  - `packages` — `all` or one of `confluence-ai`, `aspice-eval`, `aspice-check`
  - `test_pypi` — if `true`, publishes to TestPyPI instead of production

Manual dispatch does NOT create a GitHub release — only tag pushes do.

### Required Secrets

Configure in GitHub repo settings → Secrets and variables → Actions:

| Secret | Description |
|---|---|
| `PYPI_API_TOKEN` | PyPI API token (starts with `pypi-...`). Create at https://pypi.org/manage/account/token/ |

For TestPyPI uploads, the same token won't work — you'd need a separate TestPyPI token. If you need that, add a `TESTPYPI_API_TOKEN` secret and branch the workflow on `inputs.test_pypi`.

### Publish Order

Packages are published sequentially in dependency order:
1. `confluence-ai` (standalone)
2. `aspice-eval` (standalone)
3. `aspice-check` (depends on both above)

If `confluence-ai` fails to publish, `aspice-eval` and `aspice-check` are skipped.

### Versioning

Make sure `pyproject.toml` and `__init__.py` version strings match the tag before pushing. The workflow does not bump versions automatically.
