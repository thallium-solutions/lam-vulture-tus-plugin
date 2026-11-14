# @lam/vulture/tus-plugin Changelog

All notable changes to `@lam/vulture/tus-plugin` are documented here.

## [3.0.5] - 2026-11-14

### Fixed

- The completion callback documented in the README
  (`server.ctx["__tusComplete"] = lambda upload: ...`) is called. Only a
  callback whose Go type was exactly `func(map[string]interface{})` (a typed
  Lam lambda returning nothing) was recognised; the README's untyped lambda
  was silently never called. Typed and untyped lambdas, with or without a
  result, are accepted now.
- A zero-length upload (`Upload-Length: 0`) is complete when it is created
  and its completion callback runs; it stayed incomplete forever (no PATCH
  can complete it), so the callback never ran.

### Tests

- `tests/test_tus_binary_concurrent_completion.lam` (real listener): every
  byte value and a UTF-8 character split across two PATCH requests stored
  byte-exact; non-ASCII base64 metadata in the completion payload; typed and
  untyped completion callbacks (both fixes); creation-with-upload; zero-length
  uploads; `Tus-Max-Size`; a race of two PATCH requests at the same offset
  (one 204, one 409); 10 uploads sent concurrently from async tasks by an
  `Uploader` class with `?`, `do/catch` and comprehensions; a missing upload.
  Clean under `--race`.

## [3.0.4] - 2026-11-03

### Changed

- Compatible with `lamc` 4.x and `@lam/vulture` 3.0.0 (handlers may return
  `html`, `xml`, `json` or `str`): pins `@lam/vulture` 3.0.0 and declares
  `compatibility.lamc = ">=4.0, <5"` (test runner too).

## [3.0.3] - 2026-10-20

### Changed

- Compatible with `lamc` 3.x: `compatibility.lamc = ">=1.18, <4"` (test runner too).
- Pins `@lam/vulture` 2.0.3.

## [3.0.2] - 2026-10-18

### Changed

- Compatible with `lamc` 2.x: `compatibility.lamc = ">=1.18, <3"` (the test
  runner accepts the same range). Tested with `lamc` 2.0.0; no API change.
- Pins `@lam/vulture` 2.0.2.

## 3.0.1 - 2026-10-16

### Fixed

- The `@lam/vulture` dependency pointed at the tag `v2.0.0`, which is not
  published (release tags are plain versions), so installing the package from
  Git failed. It now pins `@lam/vulture` `2.0.1`, the release this package is
  tested with.

## 3.0.0 - 2026-10-15

### Removed

- **Breaking:** removed the root `tag()` helper. The package name and version
  are declared in `lamlib.toml`, and the generic top-level function made this
  package impossible to link together with any other package (or application)
  that also declared `tag()`, because all Lam modules share one Go package.

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
