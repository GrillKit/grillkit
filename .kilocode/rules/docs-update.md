# docs-update.md

---
description: Update CHANGELOG.md and README.md on significant changes
alwaysApply: true
---

# Documentation Update Requirements

When making significant changes to the project, always update:

## CHANGELOG.md

Update `[Unreleased]` section with changes following [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [Unreleased]

### Added
- New feature description

### Changed
- Behavior changes

### Fixed
- Bug fixes

### Removed
- Deprecated features removed
```

**Update when:**
- Adding new features (Added)
- Changing existing behavior (Changed)
- Fixing bugs (Fixed)
- Adding new dependencies
- Changing API/contracts

**Skip for:**
- Code formatting
- Minor refactoring without behavior change
- Test-only changes
- Documentation typo fixes

## README.md

Update when introducing:
- New major features
- Changed installation/setup steps
- New configuration options
- New dependencies or requirements

Add to appropriate section or create new if needed.
