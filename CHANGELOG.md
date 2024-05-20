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

## [0.2.0]

### Added
- Modifying a user can now accept an optional list of groups to assign to that user - to clear out a user's groups, PUT an empty list for groups

### Changed
- If permissions are ommited to a group change (i.e. not specified or None), they won't be cleared out - an empty list must be specified to do so
- The user groups and their associated permissions are now returned with the user object

## [0.1.2]

### Security
- Updated project dependencies to latest versions to fix CVEs found in `black`, `idna`, and `dnspython`

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
