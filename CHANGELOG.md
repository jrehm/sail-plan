# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.0] - 2025-01-17

### Added
- Semantic versioning with version display in UI footer
- Mobile-optimized UI with larger sail selection buttons (+33%) and headers (+50%)
- Compact sidebar history with alternating row shading and inline delete icons
- Scrollable history showing up to 50 entries
- Hour/minute dropdown selectors with 5-minute granularity for backdating
- Notes popover positioned to avoid mobile keyboard overlap

### Changed
- Backdate entry moved from sidebar to main page above UPDATE button
- History loads automatically when sidebar opens (removed Load History button)
- Improved touch targets and spacing throughout

## [0.8.0] - 2025-01-17

### Added
- Delete functionality for sail log entries to correct mistakes
- Confirmation dialog before deleting entries

## [0.7.0] - 2025-01-17

### Added
- Multi-user consistency: fresh state fetched from InfluxDB on every render
- Pending changes indicator (yellow banner) when user has unsaved changes
- Visual distinction between committed state and pending selections

## [0.6.0] - 2025-01-17

### Added
- Automatic timezone detection from Signal K GPS position
- Local time display in header, history, and backdate picker
- Timezone caching (10-minute refresh) for performance
- Fallback to UTC when GPS position unavailable

## [0.5.0] - 2025-01-16

### Added
- Project organization with Makefile, pyproject.toml
- Development tooling (ruff, mypy)
- Environment-based configuration (.env file)
- Comprehensive README documentation

## [0.1.0] - 2025-01-16

### Added
- Initial release
- Touch-friendly Streamlit interface for sail configuration logging
- InfluxDB integration for data persistence
- Main sail states: DOWN, FULL, R1-R4
- Headsail options: Jib, J1, Storm Jib (mutually exclusive)
- Downwind sails: Biggee, Reaching Spi, Whomper (mutually exclusive)
- Staysail mode (Jib + Reaching Spi combination)
- Optional backdating for missed entries
- Comment field for notes
- Recent history view

[Unreleased]: https://github.com/jrehm/sail-plan/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/jrehm/sail-plan/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/jrehm/sail-plan/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/jrehm/sail-plan/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/jrehm/sail-plan/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/jrehm/sail-plan/compare/v0.1.0...v0.5.0
[0.1.0]: https://github.com/jrehm/sail-plan/releases/tag/v0.1.0
