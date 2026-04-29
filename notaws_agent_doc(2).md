# notaws — Agent Documentation

## What is notaws

notaws is a Django-based AWS clone. It exposes two services: **EC2** (virtual machines backed by Docker containers) and **S3** (object storage). This document covers the EC2 service only — specifically `ImageBuild`, `Image`, `Instance`, and `docker_ops`.

The EC2 service is a thin management layer on top of Docker. It does not implement virtualization — it provisions Docker containers as if they were VMs. Users order instances, pick a machine image, specify resources, and get a running container they can connect to.

---

## Access Control

Two roles: **admin** and **user**.

| Resource | Admin | User |
|---|---|---|
| `ImageBuild` | Full CRUD; trigger build/rebuild; delete if not in use | No access |
| `Image` | Full CRUD; attach `active_build` | Read-only (to select when creating an instance) |
| `Instance` | Full access | Full control over own instances |

**Users never interact with `ImageBuild` directly.** The `ImageBuild` layer is an infrastructure concern managed entirely by admins, analogous to how AWS users pick an AMI without knowing its build pipeline.

### System-managed fields

The following fields on `ImageBuild` are **never set directly by anyone** — not by admins, not via API. They are mutated exclusively by build/rebuild service logic:

- `docker_image_id` — set by `build_from()` after a successful Docker build
- `deprecated` — set to `True` by `rebuild_and_replace()` on the old build
- `is_built` — derived property (`docker_image_id is not Null`); not stored

Writing to these fields outside of service logic breaks consistency guarantees. Views and serializers must not expose them as writable.

---

## Project Structure (EC2 scope)

```
notaws/
├── docker_ops/              # Docker SDK wrappers — NOT a Django app
│   ├── client.py            # Docker client singleton
│   ├── images.py            # build(), remove() for Docker images
│   ├── containers.py        # create(), start(), stop(), remove() for containers
│   ├── exceptions.py        # Custom exceptions wrapping docker.errors.APIError
│   └── utils.py             # Shared helpers
├── ec2/                     # Registered Django app — owns all migrations
│   ├── models.py            # Imports models from all subapps
│   ├── admin.py             # Registers all subapp models
│   ├── migrations/
│   ├── subapps/
│   │   ├── urls.py          # Aggregates subapp URL patterns
│   │   ├── image_builds/
│   │   │   ├── models.py
│   │   │   ├── views.py
│   │   │   ├── admin_views.py
│   │   │   ├── user_views.py
│   │   │   ├── services.py
│   │   │   └── urls.py      # app_name = 'ec2_image_builds'
│   │   ├── images/
│   │   │   ├── models.py
│   │   │   ├── views.py
│   │   │   ├── admin_views.py
│   │   │   ├── user_views.py
│   │   │   ├── services.py
│   │   │   └── urls.py      # app_name = 'ec2_images'
│   │   └── instances/
│   │       ├── models.py
│   │       ├── views.py
│   │       ├── admin_views.py
│   │       ├── user_views.py
│   │       ├── services.py
│   │       └── urls.py      # app_name = 'ec2_instances'
├── static/
│   ├── css/ec2/
│   └── js/ec2/
└── templates/ec2/
```

Subapps are Python packages, not registered Django apps. `ec2/models.py` imports their models so Django's migration system sees them under the `ec2` app. Templates and static files are centralized.

---

## Data Models

### ImageBuild

Represents one concrete build of a Docker image from a Dockerfile. `docker_image_id`, `deprecated`, and `is_built` are immutable from the outside — only service logic mutates them. `tag` and `dockerfile_code` are admin-editable, but changing `dockerfile_code` (or force-rebuilding) triggers replication rather than in-place mutation.

```
ImageBuild
    id
    tag                 # Docker image tag, e.g. "ubuntu-22.04:v3" — admin-editable
    dockerfile_code     # Raw Dockerfile text stored in DB — admin-editable
    docker_image_id     # SYSTEM-MANAGED. Set by build_from(). Null if not yet built.
    deprecated          # SYSTEM-MANAGED. Set True by rebuild_and_replace(). Default=False.
    @is_built           # SYSTEM-MANAGED. Derived property: docker_image_id is not Null.
```

### Image

Represents a generic VM template (e.g., "Ubuntu 22.04"). It is a named pointer to a current `ImageBuild`. Does not hold Dockerfile logic itself.

```
Image
    id
    name                # e.g. "Ubuntu 22.04"
    active_build        # FK -> ImageBuild, nullable
                        # The build that new instances will use
```

### Instance

Represents a running (or stopped) VM provisioned for a user.

```
Instance
    id
    docker_container_id # Docker container ID; assigned after scheduling
    name                # nullable, user-defined label
    image               # FK -> Image
    image_build_in_use  # FK -> ImageBuild — snapshot at creation time
    ram
    cpu
    storage
```

`image_build_in_use` is set at instance creation to `image.active_build` at that moment. It does **not** update when the Image's `active_build` changes. This is intentional: an instance is tied to the exact build it was started from.

---

## docker_ops

Plain Python package. Not a Django app. Imported exclusively by `services.py` files in subapps. **Never called from views directly.**

These are low-level Docker SDK wrappers — they know nothing about Django models. They take primitive types (strings, file objects), wrap Docker SDK calls, and raise custom exceptions on failure.

```python
# images.py

def build(tag: str, dockerfile_fileobj: IO) -> tuple[str, Any]:
    # Wraps docker_client.images.build()
    # pull=True is hardcoded — always pulls base image from registry before build
    # Returns (docker_image_id: str, logs)
    # Raises: ImageBuildException on any failure

def remove(image_id: str) -> None:
    # Wraps docker_client.images.remove()
    # Raises: ImageRemoveException on any failure

# containers.py

def create_container(cpu, ram, storage) -> str:
    # Returns docker container ID

# client.py
# Initializes docker.from_env() as a singleton — docker_client
```

All Docker SDK exceptions (`BuildError`, `APIError`, etc.) are caught and re-raised as custom exceptions defined in `docker_ops/exceptions.py`. Callers (service functions) handle these custom exceptions, not raw Docker SDK errors.

### Service functions vs docker_ops

These are distinct layers with different responsibilities:

| | `docker_ops` | `services.py` |
|---|---|---|
| Knows about | Docker SDK, file objects, image/container IDs | Django models, business logic, job scheduling |
| Example `build` | `build(tag, fileobj) -> (image_id, logs)` | `build_from(mib_entity)` — pulls model fields, calls `docker_ops.build()`, updates model |
| Calls | Docker SDK | `docker_ops` functions + ORM |

Example contrast for build:

```python
# docker_ops/images.py — wrapper
def build(tag: str, dockerfile_fileobj: IO) -> tuple[str, Any]:
    image, logs = docker_client.images.build(tag=tag, fileobj=dockerfile_fileobj, pull=True)
    return (str(image.id), logs)

# services.py — service function
def build_from(mib_entity: ImageBuild) -> str:
    tag = mib_entity.tag
    dockerfile_code = mib_entity.dockerfile_code
    image_id, logs = docker_ops.build(tag, File(dockerfile_code))
    return image_id
```

`pull=True` in the Docker SDK call is what performs the registry pull — it is hardcoded in the wrapper, not a caller concern.

---

## ImageBuild Lifecycle

### 1. Create (metadata only)

Creates an `ImageBuild` record in the database without invoking Docker. The record is unbuilt (`docker_image_id=Null`, `is_built=False`).

```
Input: tag, dockerfile_code
Output: ImageBuild record saved, is_built=False
```

This separates the DB record creation from the actual Docker build operation.

### 2. Build / Rebuild

The `build()` method on `ImageBuild` is the central operation. Its behavior branches on whether the build has already been built:

**Not yet built (`is_built=False`):**
```python
new_id = service.build_from(self)        # Invoke Docker, get image ID
update_docker_image_id(self, new_id)     # Set docker_image_id, save
return (self, None)
```

**Already built (`is_built=True`) — rebuild:**
```python
new_build = rebuild_and_replace(self)
return (self, new_build)
```

`rebuild_and_replace(old_build)`:
```python
new_build = create_build_from(old_build)  # Clone record, build new Docker image
old_build.deprecated = True
old_build.save()
update_image_references(old_build=old_build, new_build=new_build)
# Finds all Image records where active_build == old_build
# and sets active_build = new_build. Automatic, no admin action needed.
return new_build
```

`create_build_from(mib_entity)`:
```python
new_mib = copy(mib_entity)          # New DB record, same tag + dockerfile
new_mib.save()
image_id = build_from(new_mib)      # pulls base image from registry, then docker.build()
new_mib.docker_image_id = image_id
return new_mib
```

`build_from(mib_entity)`:
```python
tag = mib_entity.tag
dockerfile_code = mib_entity.dockerfile_code
# docker_ops.build() has pull=True hardcoded — registry pull is handled inside the wrapper
image_id, logs = docker_ops.build(tag, File(dockerfile_code))
return image_id
```

The registry pull is handled inside `docker_ops.build()` via `pull=True` on the SDK call — it is not a separate explicit step in service logic.

**Why append-only?** If a rebuild mutated `docker_image_id` on the existing record, any `Instance` with `image_build_in_use` pointing to that record would silently reference the new Docker image — meaning a running container would be linked to a build it was never started from. Creating a new record on every rebuild avoids this. Existing containers keep their `image_build_in_use` pointing to the old record and remain unaffected.

### 3. Update

Allowed fields: `tag`, `dockerfile_code`, plus an optional `force_rebuild` flag.

```python
if tag changed:
    self.tag = new_tag          # in-place, no rebuild

if dockerfile_code changed or force_rebuild:
    if dockerfile_code changed:
        self.dockerfile_code = new_dockerfile_code
    rebuild_and_replace(self)   # always triggers replication

self.save()
```

A tag change updates the record in place — no Docker operation, no replication. A Dockerfile change or `force_rebuild` always triggers `rebuild_and_replace`, which creates a new `ImageBuild` record and deprecates this one. In the `force_rebuild` case with no Dockerfile change, the new record is a clone with the same `dockerfile_code` but a fresh Docker build (pulling the latest base image from registry).

### 4. Un-build

Removes the Docker image from the host without deleting the DB record.

```python
if in CONTAINER_USE or IMAGE_USE:
    raise BUILD_IN_USE
elif build_not_exists:
    return "OK"
schedule_remove_if_exists_from(self)
self.docker_image_id = Null
```

Cannot un-build if any container or Image currently references this build.

### 5. Delete (record)

Deletes both the Docker image and the DB record.

```python
schedule_remove_if_exists_from(self)   # Schedules docker image removal
self.delete()                          # Deletes DB record
```

`schedule_remove_if_exists_from(entity)` adds a `remove(entity.id)` call to the job queue. It does not block.

### 6. Deprecated build cleanup

When a rebuild happens, the old build is marked `deprecated=True`. A background system job (`deprecated_build_clean_up_job`) periodically finds deprecated builds that are no longer referenced by any container or Image and deletes them.

This gives in-flight containers time to finish their lifetime before the old Docker image is removed.

---

## Image Lifecycle

### Create

Creates an `Image` record. `active_build` can be null initially.

### Update

Allowed fields: `name`, `active_build`.

When `active_build` is reassigned, existing instances are **not** affected — they hold `image_build_in_use` as a snapshot. Only new instances will use the new `active_build`.

If `active_build` references a build used by running containers, those containers remain on the old build.

### Delete

Prohibited if any `Instance` references this Image. Cannot delete an Image that has live instances.

---

## Instance Lifecycle

### Create

```python
def create_instance(image, ram, cpu, storage):
    # Precondition: image.active_build must be built (is_built=True)

    new_instance = Instance(
        image=image,
        image_build_in_use=image.active_build,  # snapshot
        ram=ram,
        cpu=cpu,
        storage=storage,
    )
    new_instance.save()

    new_instance.docker_container_id = schedule_container_creation_from(new_instance)
```

`schedule_container_creation_from` is async — the container ID is assigned after scheduling, not immediately. The instance record exists in the DB before the container is running.

### Update

Allowed fields: `name`, `ram`, `cpu`, `storage`.

### Operations

- `start` — also equivalent to restart
- `stop`
- `delete`
- `get_status`

Terminal attach is planned (`Later add terminal attach`).

---

## Design Decisions

1. **Deprecated build cleanup**: Periodic background job. Not event-driven — no hook fires on container deletion.

2. **Dockerfile on rebuild**: Always replicated into the new `ImageBuild` record unconditionally.

3. **Why not store `docker_image_id` directly on `Instance`**: Rejected. Append-only replication makes it unnecessary, and the `image_build_in_use` FK enables tracking which exact build each instance was started from.

---

## UI Interfaces

All templates are custom — Django's built-in admin panel is not used.

### Admin interfaces

#### ImageBuild

**List** (`admin_views.py` → `ec2_image_builds:list`)
Columns: tag, is_built, deprecated, created_at.
Per-row actions: Build (shown if `is_built=False`), Rebuild (shown if `is_built=True`), Delete (blocked if referenced by anything — any `Instance.image_build_in_use` or any `Image.active_build`).

**Detail** (`ec2_image_builds:detail`)
Displays: tag, dockerfile_code (read-only), is_built, deprecated.
Actions: Build / Rebuild (same endpoint, behavior branches on `is_built`), Delete (blocked if referenced by any Instance or Image).

**Create** (`ec2_image_builds:create`)
Form fields: tag, dockerfile_code.
On submit: creates record only — does not build. Admin must trigger build separately.

**Update** (`ec2_image_builds:update`)
Form fields: tag, dockerfile_code, force_rebuild (checkbox).
Behavior follows Update logic: tag change is in-place; dockerfile change or force_rebuild triggers replication.

#### Image

**List** (`admin_views.py` → `ec2_images:list`)
Columns: name, active_build (tag), created_at.
Per-row actions: Edit, Delete (blocked if any Instance references this Image).

**Detail** (`ec2_images:detail`)
Displays: name, active_build (linked to its ImageBuild detail page).
Actions: Edit, Delete.

**Create** (`ec2_images:create`)
Form fields: name only. `active_build` is not set at creation — admin attaches a build via Update after an `ImageBuild` exists and is built.

**Update** (`ec2_images:update`)
Form fields: name, active_build (dropdown — shows only built, non-deprecated `ImageBuild` records).

---

### User interfaces

All user-facing `ImageBuild` pages: none. Users never see this resource.

#### Image

**List** (read-only, used as input to Instance creation — no standalone page needed beyond the dropdown in the Create Instance form).

#### Instance

**Dashboard** (`user_views.py` → `ec2_instances:list`)
Table columns: Instance name, short_id, Status, View.
Actions: Show stats, + new VM.

**Create** (`ec2_instances:create`)
Form fields: Name, Choose Machine (Image dropdown), Number of CPUs, RAM, Storage.
Resource limits enforced by service config (e.g. max CPU=4, max RAM=8GB).
Precondition: selected Image must have a built, non-deprecated `active_build`.

**Detail** (`ec2_instances:detail`)
Displays: Name, ID, CPU, RAM, Storage, Storage used, Status.
Actions: Connect (terminal), Edit, Delete (schedules Docker container removal as a background job — does not block).

**Edit** (`ec2_instances:update`)
Form fields: Name, Number of CPUs, RAM, Storage.
Resource limits apply same as Create.

**Terminal** (`ec2_instances:terminal`)
Shows shell prompt. Single action: Disconnect.

---


```
docker_ops
    ↓
ec2/subapps/image_builds
    ↓
ec2/subapps/images
    ↓
ec2/subapps/instances
```

Nothing else is in scope for the current implementation phase.
