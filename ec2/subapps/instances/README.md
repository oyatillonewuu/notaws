# instances

EC2-like instance lifecycle. Each `Instance` row corresponds to a Docker
container that the owner can start, stop, resize, and connect a terminal to.

See `docs/structure.md` for the project-level subapp layout.

## Build pinning

`Instance.image_build_in_use` is set at creation to whatever
`image.active_build` was at that moment. It is never updated after, so a
running instance keeps using its original build even if the image is rebuilt
or deprecated. This is the same invariant `MachineImageBuild` provides for
ImageBuild lifecycle.

## Terminal — WebSocket protocol

`/ws/instances/<pk>/terminal/` (see `routing.py`, `consumers.py`).

| Frame type   | Direction        | Meaning                                      |
| ------------ | ---------------- | -------------------------------------------- |
| Binary       | client → server  | Raw keystrokes / paste, forwarded to the PTY |
| Text (JSON)  | client → server  | Control messages                             |
| Binary       | server → client  | PTY output, written to xterm.js              |

Control messages are JSON objects with a `"type"` field. Currently only:

```json
{"type": "resize", "rows": 24, "cols": 80}
```

Input must be sent as binary, not text. An earlier version sent input as
text and tried to detect control messages by parsing JSON — which silently
swallowed every digit (`json.loads("1")` returns the int `1`, and
`(1).get(...)` raised `AttributeError`). Binary frames sidestep the
ambiguity.

The consumer wraps `AuthMiddlewareStack` with `AllowedHostsOriginValidator`
in `notaws/asgi.py`. Any new host that should be allowed to connect must be
in `ALLOWED_HOSTS`.

## update_instance — live cgroup update, no recreate

Changing CPU or RAM on an existing instance does not recreate the container
— it calls `docker update` to adjust cgroup limits in place. Filesystem
state is preserved. Storage is label-only (see below).

## lxcfs (host requirement for the VM illusion)

Without lxcfs, `/proc/cpuinfo`, `/proc/meminfo`, `/proc/uptime`, etc. inside
containers report **host** values, not the cgroup limits we set. So `free`,
`nproc`, `neofetch`, and `fastfetch` will show the host's resources and the
"VM" illusion breaks.

`docker_ops.containers._lxcfs_volumes()` bind-mounts `/var/lib/lxcfs/proc/*`
over the container's `/proc/*` so `free`, `nproc`, `neofetch`, etc. reflect
the container's actual limits. If lxcfs isn't installed on the host the
function returns no mounts and the container starts normally — only the
illusion breaks.

Install on the host (Debian/Ubuntu):

```sh
sudo apt install lxcfs
sudo systemctl enable --now lxcfs
```

If lxcfs restarts, mounts in already-running containers go stale — those
containers need recreating.

## Known limitations

- **Storage is label-only.** `notaws.storage_gb` is recorded but not
  enforced. Real enforcement needs overlay2 + `d_type` and
  `--storage-opt size=Xg`, which is host-FS dependent.
- **No per-tenant network isolation.** Containers share the default bridge,
  so a tenant can reach another tenant's container by IP. Future work:
  per-instance network namespace.
- **Status is read on every list-page render.** One Docker API call per
  row. Fine for the demo; would batch in production.
- **`tasks.dispatch_*` are synchronous.** The names and module are set up
  for Celery, but the calls run in the request thread today. Wiring Celery
  is what the `feat/ec2-image-builds-job-queueing` branch is for.
