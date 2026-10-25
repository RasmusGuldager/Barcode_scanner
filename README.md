# VAP-LAB Rental System

Rental system for the VAP-LAB at Aalborg University. Users sign in by scanning their
AAU card, and rent and return equipment by scanning the QR labels with their phone.

## Getting started

You need a server with [Docker](https://docs.docker.com/engine/install/) and Git.

**1. Get the code**

```
git clone https://github.com/RasmusGuldager/VAP-rental.git
cd VAP-rental
```

**2. Create a certificate** (first time only)

The phone camera only works over HTTPS, so the site needs a certificate. This makes a
self-signed one in `certs/`, valid for one year:

```
./generate_cert.sh
```

If it says "permission denied", run `chmod +x generate_cert.sh` first. Phones will show
a warning for a self-signed certificate; accept it once to continue.

**3. Start the site**

```
docker compose up -d --build
```

The site is now running on ports 80 and 443 (port 80 redirects to HTTPS). The database
is created on the first start.

**4. Make yourself an admin**

Open the site, scan your AAU card and register. Then run on the server:

```
docker compose exec flask_app flask make-admin you@student.aau.dk
```

After that, you can make other users admins from the admin pages.

## Updating

```
git pull
docker compose up -d --build
```

Database changes are applied automatically when the site starts.

## Your data

Everything lives in the `data/` folder: the database (`rental.db`), the secret key
that keeps users signed in, and the backups.

**Backups.** A backup is written to `data/backups/` once a day, and the newest 30 are
kept. Admins can also make and download backups on the website under Admin > Export.
The backups are on the same disk as the database, so copy them somewhere else now and
then.

**Restoring a backup.** This replaces everything in the database with the backup:

```
docker compose exec flask_app flask import data/backups/rental-2026-10-23-142607.json --mode replace
```

## Commands

Run these on the server, from the `VAP-rental` folder:

| Command | What it does |
|---|---|
| `docker compose exec flask_app flask make-admin EMAIL` | Make a registered user an admin |
| `docker compose exec flask_app flask delete-user CARD_OR_EMAIL` | Delete a user (only if they have no rentals or notes) |
| `docker compose exec flask_app flask backup` | Write a backup now |
| `docker compose exec flask_app flask export FILE` | Write the whole database to a JSON file |
| `docker compose exec flask_app flask import FILE --mode merge` | Add and update from a JSON file; nothing is deleted |
| `docker compose exec flask_app flask import FILE --mode replace` | Delete everything, then load the file (asks first) |
| `docker compose logs -f flask_app` | Show the site's log |
| `docker compose down` | Stop the site |

## Development

To run the app on your own computer without Docker:

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
export FLASK_APP=app
.venv/bin/flask db upgrade      # create or update data/rental.db
.venv/bin/flask run --debug     # http://127.0.0.1:5000
```

The camera scanner only works over HTTPS or on `localhost`, so test scanning on your
computer, or type the codes by hand.

**Tests**

```
.venv/bin/pytest
```

**Changing the database**

After changing `app/models.py`, create a migration:

```
.venv/bin/flask db migrate -m "describe the change"
```

Check the generated file in `migrations/versions/`, then run `.venv/bin/flask db upgrade`.
Commit the migration together with the model change; the server applies it on its
next start.
