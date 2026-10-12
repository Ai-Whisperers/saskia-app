# Contributing to {{PROJECT_NAME}}

Thank you for your interest in contributing!

## Code of Conduct

This project follows our [Code of Conduct](https://github.com/Ai-Whisperers/.github/blob/main/CODE_OF_CONDUCT.md).

## How to Contribute

### Report a Bug
1. Check existing issues to avoid duplicates
2. Use the Bug Report issue template
3. Include: steps to reproduce, expected vs actual behavior, logs

### Submit a Change
1. **Branch:** Create from `main`
   - `feat/` — new features
   - `fix/` — bug fixes
   - `docs/` — documentation
   - `refactor/` — code restructuring
   - `chore/` — maintenance
2. **Commit:** Use [Conventional Commits](https://www.conventionalcommits.org/)
   ```
   feat: add user authentication
   fix: resolve memory leak
   docs: update API reference
   ```
3. **Test:** Ensure tests pass
4. **Open PR:** Use the pull request template

## Development Setup

```bash
git clone https://github.com/Ai-Whisperers/{{PROJECT_SLUG}}.git
cd {{PROJECT_SLUG}}
# Install dependencies
pip install -r requirements-dev.txt
pre-commit install
```

## Code Style

- Python: Follow PEP 8, use `ruff` for formatting and linting
- Type hints for function signatures
- Docstrings for public functions
- Run `ruff check . && ruff format .` before committing

## Security

**Never commit secrets or credentials.** Use environment variables.
