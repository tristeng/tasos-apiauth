# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.1.1] - 2024-03-17

### Added

- Changelog file

### Changed

- Updated URLs in `pyproject.toml` file
- Added a mypy ignore for missing import for the `httpx` package

### Security

- Updated `fastapi` in order to patch `CVE-2024-24762` introduced by dependency `starlette`: python-multipart vulnerable to Content-Type Header ReDoS

## [0.1.0] - 2024-02-03

### Added

- Initial release
