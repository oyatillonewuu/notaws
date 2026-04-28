# notaws — Project Structure

## Overview

notaws is a Django-based AWS clone exposing two services: **EC2** (virtual machines via Docker) and **S3** (storage). The project uses a sub-app-inside-app architecture for EC2 due to tight coupling between `Image`, `ImageBuild`, and `Instance` models.

---

## Directory Layout

```
notaws/
├── docker_ops/          # Docker client + primitive wrappers
├── docs/                # Design documents and diagrams
├── ec2/                 # EC2 Django app (registered in INSTALLED_APPS)
│   ├── subapps/         # Internal sub-modules (not registered)
│   │   ├── dashboard/
│   │   ├── home/
│   │   ├── image_builds/
│   │   ├── images/
│   │   ├── instances/
│   │   └── urls.py      # Aggregates all subapp URL patterns
│   ├── migrations/      # All EC2 migrations live here
│   ├── models.py        # Imports models from all subapps
│   ├── urls.py          # Delegates to subapps/urls.py
│   └── views.py
├── notaws/              # Django project settings
├── static/              # Centralized static files
│   ├── css/
│   │   ├── base.css
│   │   └── ec2/
│   └── js/
│       ├── base.js
│       └── ec2/
├── templates/           # Centralized templates
│   └── ec2/
│       ├── dashboard/
│       ├── home/
│       ├── image_builds/
│       ├── images/
│       └── instances/
└── manage.py
```

---

## docker_ops

Primitive wrappers around the Docker Python SDK. Not a Django app — plain Python package imported by EC2 service layers.

| File | Responsibility |
|------|----------------|
| `client.py` | Initializes and exposes the Docker client singleton |
| `images.py` | Wraps `build`, `remove` on Docker images |
| `containers.py` | Wraps `create`, `start`, `stop`, `remove` on containers |
| `exceptions.py` | Custom exceptions wrapping `docker.errors.APIError` |
| `utils.py` | Shared helpers (e.g. status code inspection) |

---

## EC2 App

The only Django app registered in `INSTALLED_APPS`. Owns all migrations and model registration. Internally structured as subapps to reflect domain boundaries.

### Why subapps are not registered

Subapps are Python packages, not Django apps. They are not in `INSTALLED_APPS` because:

- `ec2/models.py` imports all their models — migrations are handled by the `ec2` app.
- `collectstatic` and template discovery operate on registered apps only; both are centralized instead.
- Django app machinery (`apps.py`, `admin.py`) is irrelevant for internal modules.

### Model ownership

```
ec2/models.py
    from ec2.subapps.images.models import Image
    from ec2.subapps.image_builds.models import ImageBuild
    from ec2.subapps.instances.models import Instance
```

All migrations are generated into `ec2/migrations/`.

### Admin

Subapp models are registered in `ec2/admin.py`, not inside individual subapps.

---

## URL Routing

Three-layer delegation:

```
notaws/urls.py
    path('ec2/', include('ec2.urls'))

ec2/urls.py
    path('', include('ec2.subapps.urls'))

ec2/subapps/urls.py
    path('images/',    include('ec2.subapps.images.urls'))
    path('builds/',    include('ec2.subapps.image_builds.urls'))
    path('instances/', include('ec2.subapps.instances.urls'))
    path('dashboard/', include('ec2.subapps.dashboard.urls'))
    path('',           include('ec2.subapps.home.urls'))
```

Each subapp's `urls.py` declares `app_name` for namespacing. Names are prefixed with `ec2_` to avoid collisions with future apps (e.g. s3):

| Subapp | app_name |
|--------|----------|
| images | `ec2_images` |
| image_builds | `ec2_image_builds` |
| instances | `ec2_instances` |
| dashboard | `ec2_dashboard` |
| home | `ec2_home` |

Template usage: `{% url 'ec2_images:list' %}`, `{% url 'ec2_instances:create' %}`.

---

## Subapp Structure

Each subapp contains only what it needs. Standard Django files (`apps.py`, `migrations/`) are omitted since the subapp is not a registered app.

```
subapp/
├── __init__.py
├── models.py       # Model definitions (imported by ec2/models.py)
├── views.py        # View dispatch (imports admin_views / user_views)
├── admin_views.py  # Views for admin-facing operations
├── user_views.py   # Views for user-facing operations
├── services.py     # Business logic and docker_ops calls
└── urls.py         # URL patterns + app_name
```

---

## Static Files

Centralized under `static/`. `STATICFILES_DIRS = [BASE_DIR / 'static']`.

```
static/
├── css/
│   ├── base.css          # Global styles, loaded in base.html
│   └── ec2/
│       ├── common.css    # Shared EC2 styles
│       ├── images.css
│       ├── image_builds.css
│       ├── instances.css
│       ├── dashboard.css
│       └── home.css
└── js/
    ├── base.js           # Global scripts
    └── ec2/
        ├── images.js
        ├── image_builds.js
        ├── instances.js
        └── dashboard.js
```

Subapp-specific files are loaded only in templates that need them. `base.css` and `base.js` are loaded once in `base.html`.

---

## Templates

Centralized under `templates/`. `TEMPLATES[0]['DIRS'] = [BASE_DIR / 'templates']`.

Templates are referenced explicitly in views:

```python
template_name = 'ec2/instances/list.html'
```

---

## Build Order

Dependencies between components:

1. `docker_ops` — no dependencies, build first.
2. `ec2/subapps/image_builds` — no inter-subapp dependencies.
3. `ec2/subapps/images` — depends on `image_builds`.
4. `ec2/subapps/instances` — depends on `images` and `image_builds`.
5. `ec2/subapps/dashboard` — depends on `instances`.
6. `ec2/subapps/home` — independent.

Parallel build path: `home` and `docker_ops` can proceed independently of the `image_builds → images → instances → dashboard` chain.
