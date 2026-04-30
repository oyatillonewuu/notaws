Running:

```
  docker compose up --build
  docker compose exec web python manage.py migrate
  docker compose exec web python manage.py createsuperuser
```
