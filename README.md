# VAP-LAB Rental System

Rental system for the VAP-LAB at Aalborg University. Users identify by scanning their
AAU card, and rent and return items by scanning QR labels with their phone.

See `PLAN.md` for the design and the task list.

## Development

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
export FLASK_APP=app
.venv/bin/flask db upgrade      # create or update data/rental.db
.venv/bin/flask run --debug     # http://127.0.0.1:5000
.venv/bin/pytest                # run the tests
```

The camera scanner only works over HTTPS (or on `localhost`).

### Changing the database

After changing `app/models.py`:

```
.venv/bin/flask db migrate -m "describe the change"
```

Check the generated file in `migrations/versions/`, then run `flask db upgrade`.

## Deployment

```
./generate_cert.sh        # self-signed certificate in certs/ (first time only)
docker compose up -d --build
```

The site is served on ports 80/443. The database and the secret key live in `data/`;
back up that folder. Migrations are applied automatically when the container starts.

## Export, import and backups

```
flask export data.json                    # whole database as JSON
flask import data.json --mode merge       # add/update, never deletes
flask import data.json --mode replace     # wipe, then load (asks first)
flask backup                              # dated copy in data/backups/, keeps 30
```

In Docker, prefix these with `docker compose exec flask_app`. The `backup` service in
`docker-compose.yml` runs `flask backup` once a day. Admins can do the same from the
website under Admin > Export.

## Admins

Admins are normal users with extra rights. To make the first admin, register on the
site by scanning your card, then run on the server:

```
docker compose exec flask_app flask make-admin you@example.com
```

After that, admins can promote other users from the admin pages.

To delete a user (only possible if they have no rentals or notes):

```
docker compose exec flask_app flask delete-user 123456          # card number or email
```
