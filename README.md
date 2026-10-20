# @lam/vulture/tus-plugin

`@lam/vulture/tus-plugin` adds server-side
[tus 1.0](https://tus.io/protocols/resumable-upload) resumable uploads to
[`@lam/vulture`](https://github.com/thallium-solutions/lam-vulture), the HTTP
server package for the
[Lammergeier programming language](https://github.com/thallium-solutions/lammergeier-lang).
It was extracted from Lammergeier's central `lib/lamserver_tus.lam` module so the
protocol plugin can be installed, versioned, and tested independently of the
compiler.

## Features

- Core tus creation, `HEAD`, `PATCH`, and termination flows.
- Creation-with-upload for a first chunk sent with `POST`.
- Concatenation with `Upload-Concat: partial` and `final;...`.
- Per-chunk `sha1`, `sha256`, and `md5` checksum verification.
- Per-upload locking for parallel `PATCH` offset safety.
- Durable JSON metadata and append-only blob storage on the local filesystem.
- A completion callback for application-specific scanning, moves, or processing.
- Explicit garbage collection through `tusGc`.
- In-process testing through `@lam/vulture`'s `Server.inject` API.

The plugin advertises:

```text
Tus-Version: 1.0.0
Tus-Extension: creation,creation-with-upload,termination,concatenation,checksum
Tus-Checksum-Algorithm: sha1,sha256,md5
```

## Requirements

- Lammergeier compiler (`lamc`) 1.18.0 or newer, including 2.x
  (`>=1.18, <4`).
- `@lam/vulture` 2.0.2. The release Git ref is pinned in `lamlib.toml`.
- `github.com/google/uuid` v1.6.0. This matches the version used by the former
  central standard-library module.

## Installation

Install the 3.0.1 Git release directly:

```bash
lamc install https://github.com/thallium-solutions/lam-vulture-tus-plugin.git@3.0.1
```

After registry publication, install by scoped package name:

```bash
lamc install @lam/vulture/tus-plugin@3.0.1
```

The package manifest resolves `@lam/vulture` from its pinned 2.0.1 Git ref.
Applications import the plugin and the core server separately:

```lammergeier
from @lam/vulture import Server
from @lam/vulture/tus-plugin import tusUploads, tusGc
```

For sibling-checkout development, use project-level path replacements:

```toml
[dependencies]
"@lam/vulture/tus-plugin" = { path = "../lam-vulture-tus-plugin" }

[replace]
"@lam/vulture" = { path = "../lam-vulture" }
```

Then run `lamc install`. This repository's test runner does not modify global
package state: it stages both sibling checkouts into an isolated `extlibs` tree.

## Quick start

```lammergeier
from @lam/vulture import Server
from @lam/vulture/tus-plugin import tusUploads

func main() {
    server: Server = Server()

    # Mount routes below /uploads, store data under ./var/uploads, and reject
    # declared upload lengths above 200 MiB.
    _ = tusUploads(server, "/uploads", "./var/uploads", 200 * 1024 * 1024).unwrap()

    _ = server.listen(8080).unwrap()
}
```

Point a tus client at `http://localhost:8080/uploads`. A completed upload's raw
bytes are stored at `./var/uploads/<id>`.

For example with `tus-js-client`:

```javascript
const upload = new tus.Upload(file, {
  endpoint: "http://localhost:8080/uploads",
  metadata: { filename: file.name, filetype: file.type },
  chunkSize: 8 * 1024 * 1024,
  retryDelays: [0, 1000, 3000, 5000],
});
upload.start();
```

## API

### `tusUploads`

```lammergeier
func tusUploads(server: Server, mountPath: str, storeDir: str, maxBytes: int) -> Result[bool]
```

Registers these routes:

| Method | Route | Purpose |
| --- | --- | --- |
| `OPTIONS` | `<mount>` | Advertise versions, extensions, checksums, and maximum size |
| `POST` | `<mount>` | Create a normal/partial upload or assemble a final upload |
| `HEAD` | `<mount>/:id` | Return current offset, length, metadata, and concat state |
| `PATCH` | `<mount>/:id` | Validate and append the next chunk |
| `DELETE` | `<mount>/:id` | Remove the blob and metadata pair |

`mountPath` must be an absolute URL path without a trailing slash. `storeDir`
is created with mode `0755` if it does not exist. `maxBytes` is compared against
the declared `Upload-Length` and the total final-concatenation length; use `0`
for no plugin-level maximum. Invalid configuration and directory-creation
failures return `Result.Err(TusConfigurationError)`; route registration succeeds
with `Result.Ok(true)`. This unsuffixed Result API replaces v1's stderr message
and silent early return.

The plugin registers typed handlers through `@lam/vulture` v2's verb overloads
and `RouteOptions`. POST and PATCH use `maxBytes` as their route body limit in
addition to tus's declared-length checks.

### `tusGc`

```lammergeier
func tusGc(storeDir: str, maxAgeHours: int) -> Result[int]
```

Deletes blob/metadata pairs whose metadata creation time is older than the
configured age and returns the number removed through `Result.Ok`. Directory
reads, malformed metadata, and removal failures return `Result.Err(TusGcError)`
instead of being skipped or collapsed into a partial count. The plugin does not
run a background expiry task.

```lammergeier
from @lam/vulture/tus-plugin import tusGc

removed: int = tusGc("./var/uploads", 72).unwrap()
print(f"removed {removed} uploads older than three days")
```

## Configuration examples

### Unlimited development endpoint

```lammergeier
_ = tusUploads(server, "/uploads", "./tmp/uploads", 0).unwrap()
```

An unlimited endpoint is convenient for local development but is generally
unsafe for an Internet-facing service. Set an application-specific maximum in
production and also configure request-body limits at the reverse proxy.

### Separate stores and limits

```lammergeier
_ = tusUploads(server, "/avatars", "./var/uploads/avatars", 10 * 1024 * 1024).unwrap()
_ = tusUploads(server, "/videos", "./var/uploads/videos", 2 * 1024 * 1024 * 1024).unwrap()
```

Use distinct directories when different upload classes have different
retention, ownership, quotas, or post-processing requirements.

### Completion processing

The callback receives `id`, `length`, `offset`, `metadata`, and `path`. A final
concatenated upload additionally includes `concat` and `parts`.

```lammergeier
from @lam/vulture import Server
from @lam/vulture/tus-plugin import tusUploads

server: Server = Server()
server.ctx["__tusComplete"] = lambda upload: print(f"ready: {upload['path']}")
_ = tusUploads(server, "/uploads", "./var/uploads", 200 * 1024 * 1024).unwrap()
```

Completion callbacks run after metadata is marked complete. Keep callbacks
short; enqueue expensive antivirus scans, transcoding, or object-store copies
onto application workers. Callback panics are recovered so they cannot corrupt
the protocol response.

## Security example

The plugin performs tus protocol handling, not authentication or authorization.
Protect the mount with an `@lam/vulture` request hook before registering the
routes:

```lammergeier
from @lam/vulture import Server, Request, Response
from @lam/vulture/tus-plugin import tusUploads

func requireUploadToken(request: Request, response: Response) {
    if request.path.startsWith("/uploads") and request.header("Authorization") != "Bearer replace-me" {
        response.setStatus(401)
        response.text("unauthorized")
    }
}

server: Server = Server()
server.onRequest(requireUploadToken)
_ = tusUploads(server, "/uploads", "/srv/myapp/uploads", 200 * 1024 * 1024).unwrap()
_ = server.listen(8080).unwrap()
```

Replace the literal token with your normal identity and policy layer. In
production:

- Authenticate every `POST`, `HEAD`, `PATCH`, and `DELETE`, and verify that the
  caller owns the referenced upload ID.
- Terminate TLS at `@lam/vulture` or a trusted reverse proxy.
- Restrict CORS at the proxy if `Access-Control-Allow-Origin: *` is not
  appropriate for your application.
- Set both `maxBytes` and reverse-proxy/body limits; quotas and free-space
  monitoring remain application responsibilities.
- Use a dedicated, non-web-served storage directory owned by the service user.
- Treat `Upload-Metadata` as untrusted input. Never use client filenames as
  filesystem paths without sanitization.
- Scan completed content before publishing or processing it.
- Schedule `tusGc` and monitor failures so abandoned partial uploads do not
  exhaust disk space.

## Storage layout and lifecycle

Each upload has a UUID identifier and two sibling files:

```text
storeDir/
├── 0b49...f5c7          # raw bytes received so far
├── 0b49...f5c7.json     # length, offset, metadata, timestamps, concat state
├── 5a9e...72af
└── 5a9e...72af.json
```

Example metadata:

```json
{
  "id": "0b49b79f-f4da-40b0-a055-c3b54674f5c7",
  "length": 11,
  "offset": 11,
  "metadata": { "filename": "hello.txt" },
  "complete": true,
  "createdAt": "2026-01-01T12:00:00Z",
  "finishedAt": "2026-01-01T12:00:01Z"
}
```

Writes append to the blob first and persist the new offset afterward. Open,
write, close, and metadata failures are represented internally as typed Results
and become explicit `500` responses; metadata-write failures attempt to truncate
the blob back to its previous size. A per-upload mutex serializes concurrent
patches in one server process. The flat
filesystem backend is deliberately simple: it does not provide shared locks
between multiple processes, distributed/object storage, encryption at rest,
free-space quotas, or automatic retention.

### Move completed uploads

```lammergeier
server.ctx["__tusComplete"] = lambda upload: print(
    f"move {upload['path']} to durable storage using id {upload['id']}"
)
```

When moving a blob, coordinate cleanup of its `.json` metadata and ensure a
client can no longer issue `HEAD`, `PATCH`, or `DELETE` for that upload. A safer
common pattern is to copy/scan first, publish the durable object atomically,
and let a retention job remove the tus pair later.

### Multiple server processes

Do not point multiple independent processes at the same `storeDir`: in-process
mutexes cannot coordinate their offsets. Use one upload owner per store, sticky
routing to a single owner, or a storage adapter designed with cross-process
locking before scaling horizontally.

## Protocol notes and limitations

- The package implements tus 1.0.0 Creation, Creation With Upload,
  Termination, Concatenation, and Checksum.
- Checksum mismatch returns the tus-recommended non-standard status `460`.
- Final concatenated uploads are immutable and return `403` to `PATCH`.
- Deferred length (`Upload-Defer-Length`), expiration, protocol-level quotas,
  distributed locks, and remote storage backends are not implemented.
- `tusGc` ages uploads from creation time, whether complete or incomplete.
- Completion callbacks are process-local and are not a durable job queue.

## Testing

The tests are ports of the central `lamserver_tus` and `lamserver_tus_ext`
cases. They stage this checkout and the sibling `../lam-vulture` checkout as
scoped packages, compile each case without cache, execute it, and compare exact
output expectations.

```bash
python3 tests/run_tests.py --verbose
```

Optionally compile with Go's race detector:

```bash
python3 tests/run_tests.py --verbose --race
```

No tests bind a network port; all protocol calls use `Server.inject` and clean
up their temporary storage.

## License

Apache-2.0.
