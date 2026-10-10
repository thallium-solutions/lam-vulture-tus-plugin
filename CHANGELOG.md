# @lam/vulture/tus-plugin Changelog

All notable changes to `@lam/vulture/tus-plugin` are documented here.

## 2.0.0 - 2026-09-30

### Added

- Typed failure tests for invalid mount configuration, missing/corrupt garbage-
  collection stores, and failed chunk persistence.
- Typed `RouteOptions` metadata and body limits on the v2 route overloads.

### Changed

- **Breaking:** `tusUploads(...)` now returns `Result[bool]`. Invalid arguments
  and store-directory creation failures return `TusConfigurationError` instead
  of writing to stderr and silently leaving the server unconfigured.
- **Breaking:** `tusGc(...)` now returns `Result[int]`. Directory reads, metadata
  decoding, and removals fail explicitly rather than returning zero, skipping
  entries, or returning a partial count.
- Chunk appends now propagate open, stat, write, close, and metadata persistence
  failures. Metadata-write failures attempt to roll the blob back to its prior
  size, and HTTP handlers return an explicit error response.
- Split the single native handler-registration block into typed Lam request
  orchestration plus focused native filesystem/checksum helpers.
- Migrated route registration to `@lam/vulture` v2's typed verb overloads and
  `RouteOptions`.
- Updated tests to use typed `InjectResponse` and unsuffixed Result APIs.
- Raised compatibility to Lam 1.18, updated `@lam/vulture` to v2.0.0, and bumped
  this package to v2.0.0.
- Plugin source uses the v2 `init` constructor convention; no legacy
  constructors remain.

### Testing

- Added an installed-package ephemeral-server lifecycle covering setup/GC
  Results, creation, empty and conflicting chunks, completion, and collection.

## 1.0.0 - 2026-09-18

### Added

- Initial standalone tus 1.0 plugin release for `@lam/vulture` v1.
