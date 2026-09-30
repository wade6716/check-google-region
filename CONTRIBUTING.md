# Contributing to check-google-region

Thank you for considering contributing to `check-google-region`!

## Development Setup

This project uses modern Python standards with **zero third-party runtime dependencies**.

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/wade6716/check-google-region.git
   cd check-google-region
   ```

2. Run with [uv](https://github.com/astral-sh/uv) or standard Python:
   ```bash
   uv run check-google-region --check
   ```

3. Run the unit test suite:
   ```bash
   python -m unittest discover tests
   ```

## Pull Request Guidelines

- Ensure all existing tests pass (`python -m unittest discover tests`).
- Keep runtime dependencies at **zero** (standard library only).
- Keep cross-platform compatibility intact (Windows, Linux, macOS).
- Update the documentation (`README.md` and `README_EN.md`) if introducing new flags or configurations.
