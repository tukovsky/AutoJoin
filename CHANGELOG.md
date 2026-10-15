# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- The version is shown in the window title and written to the log at start.
- Release pipeline: tests must pass before the exe is built, the release gets a SHA256 checksum file and generated release notes.
- Security checks: CodeQL, gitleaks, pip-audit, Dependabot.
- CI runs on Python 3.10 and 3.12 with a coverage report.

### Changed
- Dependencies in `requirements.txt` are pinned to exact versions so that Dependabot can update them.

## [0.2.2]

### Fixed
- The program crashed on every launch after the first one when `meetings.json` already existed.

## [0.2.1]

### Added
- Import of a timetable from an iCal (`.ics`) file.
- Green check / red cross to switch a meeting on or off.
- Russian and English interface with a language switch.
- Protection against failures: retries, waiting for the internet, rejoin after a dropped connection, the computer stays awake, a single instance, safe saving of `meetings.json`.
