# Contributing to CamoClaw

Thank you for your interest in contributing. This document covers how to submit PRs, code style, and testing.

---

## How to Submit a PR

1. **Fork** the repository and clone your fork locally.
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   # or: fix/your-bug-fix
   ```
3. **Make your changes** and ensure they follow the [code style](#code-style) below.
4. **Commit** with clear messages:
   ```bash
   git add .
   git commit -m "feat: add X"   # or fix:, docs:, refactor:, etc.
   ```
5. **Push** to your fork and open a **Pull Request** against `main`.
6. In the PR description, include:
   - What changed and why
   - Config notes or sanitized logs if relevant (do **not** include API keys or `.env`)
   - Any breaking changes or migration steps

---

## Code Style

- **Python**: Follow PEP 8. Use 4 spaces for indentation.
- **Line length**: Prefer ≤ 120 characters; break long lines when readability suffers.
- **Imports**: Group as `stdlib` → `third-party` → `local`, separated by blank lines.
- **Naming**:
  - `snake_case` for functions and variables
  - `PascalCase` for classes
  - `UPPER_SNAKE` for constants
- **Docstrings**: Use for public functions/classes; prefer concise one-liners where sufficient.
- **JSON configs**: 2-space indent, trailing commas allowed where supported.

---

## Testing

- **Manual testing**: Run the quickstart before submitting:
  ```bash
  python camoclaw/main.py camoclaw/configs/simple_task_config.json
  ```
- **Evolution workflow**: If your changes touch evolution logic, run:
  ```bash
  python scripts/single_task_evolve.py \
    --config-run1 camoclaw/configs/single_task_debug_run1.json \
    --config-run2 camoclaw/configs/single_task_debug_run2.json
  ```
- **No automated tests yet**: The project currently relies on manual runs. Adding `pytest` or similar is welcome.

---

## Security

- **Never** commit `.env`, API keys, or runtime data.
- Do not include sensitive logs or paths in PRs.
- See [.env.example](.env.example) for required variables.

