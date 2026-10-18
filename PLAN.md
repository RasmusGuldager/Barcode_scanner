# VAP-LAB Rental System — Rewrite Plan

This file tracks the plan for rewriting the system from scratch. Tick boxes as we go,
and add or remove items as decisions change.

## Context

- Runs on a local server at Aalborg University, reachable only from inside eduroam.
- About 30–50 users. At least one admin is always present in the lab.
- Security is not a major concern. We only need to stop normal users from changing
  the inventory.
- We're starting fresh: no old data to keep, no existing labels, and the old code is
  only a reference.
- There are many identical items (e.g. Basler ace #1–#15). Each one has its own QR
  label and its own container.
- The server is on the local network. It technically has internet access, but the app
  must not depend on it: no CDNs, no external fonts, no external API calls.

## Goals

1. **Two roles**
   - **Users** rent items, return them and leave short comments.
   - **Admins** manage the inventory and users. Any admin can promote or demote other
     admins. The first admin is promoted with a CLI command on the server.
2. **Real URLs**: every screen is its own page. No hiding and showing `div`s.
3. **QR labels on every item**: scanning a label is how users rent and return.
4. **Export and import**: dump the whole database to a text file and rebuild it from
   that file on another computer.
5. **Dimensions and containers**: store each item's size and the container it belongs
   in, so items are easy to find and can be sorted when designing 3D-printed
   containers.
6. **Automatic backups**: lightweight, since the database is small.
7. **Maintainable code**: clear structure, tests and database migrations.

---

## Decisions made

| Topic | Decision |
|---|---|
| Item identity | Each physical item has its own QR label and record, e.g. "Basler ace #5". |
| Products | A **product** is a kind of equipment (e.g. a camera model) and holds everything that is the same for all copies: name, category, specs, description and size. An **item** is one physical copy: code, number, container, rentals, notes. Same idea as asset models vs. assets in Snipe-IT. A product can only be deleted when it has no items, also counting the trash. |
| Categories and specs | Categories are records of their own. Each category has **spec fields** defined by admins on `/admin/categories`, e.g. Camera: Shutter, Max frame rate. Field types: **choice** (fixed list of options, e.g. Global / Rolling), **number** (with a unit, e.g. fps), **text** (searchable, not a filter). The type is fixed once created. Renaming an option keeps it on every product. An empty value means unknown. |
| Filtering | The public item list (`/items`) shows one row per product with "N of M available". Category tabs at the top; choosing one shows its specs as table columns and as filters (checkboxes for choices, min/max for numbers). Only available products by default. Filters live in the URL (`?category=Camera&shutter=Global&max_frame_rate_min=60`), so a filtered list can be shared. Products with an unknown value for a filtered spec are left out, with a note saying how many. No reservations: "available" means available now. |
| Item code | A random 6-character code made when the item is created, e.g. `K7F2Q8`. It never changes and is the item's permanent ID, also in exports. |
| QR content | Only a prefixed code, e.g. `VAP-K7F2Q8`. There's no URL, so labels keep working if the server address changes. |
| Scanning | The in-browser scanner is the only way to scan items. The QR code on the locker is the only one holding a full URL. |
| Returns | Only the user who rented an item can return it. If the item has a container, they scan the item and then the container label, and the return only counts if it's the right container. Items without a container are returned with just the item scan. |
| Containers | A container holds exactly one item. Containers are records of their own with a QR label (`BOX-<code>`) and a readable name/location (e.g. "Shelf B3, box 05"). An item may have no container; an admin can assign one at any time, even while the item is rented. |
| User identity | The card scan gives only a card number, so users create a short profile the first time they scan. |
| Item name | Items have a readable name as well as the code. |
| Item number | Assigned automatically, never typed in: the next free number among the product's items (counting trashed items). Renaming a product keeps the numbers. Moving an item to another product (to fix a mistake) gives it the next number there. The database enforces that product + number is unique, and product names are unique ignoring upper/lower case. |
| Adding items | "Add product" creates a product with N copies. While typing the name, existing products with similar names are shown (also with typos), with an "Add copies" link to that product. Category is chosen from existing ones or typed as a new one; choosing it swaps in that category's spec inputs. |
| Comments | Kept minimal: a short note on an item. No threads and no workflow. |
| Old data | Not migrated. We start with an empty database. |
| Who can rent | Only people with an AAU card. Non-AAU users may come later (see Open ideas). |
| Card number | The card has a regular barcode holding a 6-digit number. We validate `^\d{6}$`. |
| Study number | A different number from the card: 8 digits, typed in when registering. We validate `^\d{8}$`. |
| Profile fields | Email and study number are required. Name is optional. |
| Devices | Users use their own phones. No shared device, so no automatic logout. |
| Dimensions | Length × width × height in mm. |
| Language and tone | English only. Plain, professional wording: no emojis, no jokey messages. |
| QR prefix | `VAP-` for items, `BOX-` for containers. |
| Admins | No owner role. Any admin can promote or demote other admins in the web UI. The first admin registers like a normal user, then someone on the server runs `flask make-admin <email>`. This also rescues a setup with no admins. An admin can't demote themselves, so there is always at least one. |
| Admin login | For now, admins identify by card scan like everyone else; no password. If the user is marked admin, the admin pages are available. A password step may be added later. |
| Privacy | Only admins see who rented an item or wrote a note. Everyone else sees "Rented out", and error messages never name the renter. |
| New card | Admins can edit a user's profile, including the card number, on `/admin/users/<id>/edit`. |
| Labels | Small QR stickers. Exact size and printer decided later. |
| Internet | Everything is served locally. All JS/CSS libraries are copied into `static/vendor/`. |
| Branch | The rewrite happens on the `dev` branch. `main` keeps the old code running until the new one is ready. |
| Admin force-return | Admins can mark any open rental as returned (lost card, item left on the desk). The rental records which admin closed it. |
| Deleting items | Items go to a **trash** first, like a desktop recycle bin. Trashed items are hidden everywhere and can't be rented, but their history stays. From `/admin/trash` an admin can restore an item or delete it permanently. |

### How scanning works

1. The user scans the **locker QR code** with their phone camera. It holds the full
   site URL and opens the start page.
2. They identify once by scanning their card. A session cookie remembers them.
3. **Rent:** on `/rent` they scan item labels with the camera inside the page, one
   after another, and then confirm "Rent".
4. **Return:** they scan an item. If it has a container, the page says which one; they
   scan that container's label. If it matches, the item is returned. If not, the page
   says "Wrong container. This item belongs in <name>." Items without a container are
   returned straight away. Repeat for each item.

### QR label format

```
<PREFIX>-<CODE>      e.g.  VAP-K7F2Q8   (item)
                           BOX-M4T9XC   (container)
```

- The prefix tells the scanner what kind of label it is. Anything without a known
  prefix is rejected with "This QR code is not part of the rental system".
- The database stores only the code (`K7F2Q8`). The prefix exists only on the label.
- Codes use only uppercase letters, digits and `-`. That lets the QR use its compact
  "alphanumeric" mode, which keeps labels small.
- Code alphabet: `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, with no `0/O`, `1/I/L`, so a code
  can also be typed by hand if a label is damaged. We check for duplicates when
  creating an item or container. Containers use random codes too, so renaming or
  moving a container never invalidates its label.

---

## Proposed architecture

| Concern | Choice | Why |
|---|---|---|
| Web framework | **Flask** with blueprints (app factory) | Small and well known. Good fit for a server-rendered app this size. |
| Pages | **Jinja templates** with one URL per page, plus **htmx** for small interactive parts | Real URLs and the back button work. Almost no custom JS. |
| Database | SQLite + **SQLAlchemy 2.0** (typed models) | No extra server needed, and it handles the load easily. |
| Migrations | **Alembic** (via Flask-Migrate) | The schema will keep changing, and existing data should survive each change. |
| Forms | **Flask-WTF / WTForms** | Validation and CSRF protection without extra work. |
| Login | Flask session cookie holding the user id | Card scan identifies everyone, admins included. No passwords for now. |
| CSS | **Pico.css** (classless), or one small hand-written stylesheet | Looks clean with very little CSS. |
| Barcode scanning | **zxing-wasm** (zxing-cpp as WebAssembly), copied into `static/vendor/`, with our own small camera loop in `static/js/scanner.js` | Reads QR labels and the 1D card barcode. html5-qrcode was tried first but failed on ~5% of our labels in a browser test; zxing-wasm read 200/200. Works without internet. |
| QR generation | **segno** (pure Python) | Makes SVG labels for printing. |
| Tests | **pytest** | Covers the rent/return rules and the export/import round trip. |
| Deployment | Docker Compose: gunicorn + nginx (HTTPS) | Same setup as now, which already works. |

### Proposed layout
```
app/
  __init__.py          # create_app()
  models.py
  extensions.py        # db, migrate, csrf
  rental/              # user-facing blueprint (identify, rent, return, comments)
  admin/               # admin blueprint (items, containers, users, labels, export/import)
  services/            # business logic (rent/return rules, export/import, backup)
  templates/
  static/
migrations/
tests/
```
CLI commands: `flask make-admin <email>`, `flask export`, `flask import`, `flask backup`

### URL map (draft)
| URL | Who | Purpose |
|---|---|---|
| `/` | everyone | Start page: scan your card |
| `/identify` | everyone | Card scan → known user is remembered; unknown card goes to `/register` |
| `/register` | new user | Profile: name, email, study/employee number |
| `/me` | user | My current rentals, and a button to start scanning |
| `/rent` | user | Scanner: scan items, then "Rent N items" |
| `/return` | user | Scanner: scan an item, then its container (if it has one) |
| `/i/<code>` | everyone | Item page: name, container, status, product specs, comments, Rent button (linked from lists and history) |
| `/items` | everyone | Products with "N of M available", filtered by category, availability and specs |
| `/products/<id>` | everyone | Product page: specs, and each copy with its status and container |
| `/logout` | user | Forget who this phone belongs to ("not you?") |
| `/admin/items`, `/admin/items/<id>/edit` | admin | Physical copies: container, product, trash |
| `/admin/products`, `/admin/products/new`, `/admin/products/<id>/edit` | admin | Products: name, category, specs, size, and adding copies |
| `/admin/categories`, `/admin/categories/<id>/edit`, `/admin/fields/<id>/edit` | admin | Categories, their spec fields and options |
| `/admin/containers`, `/admin/containers/new`, `/admin/containers/<id>/edit` | admin | Container management |
| `/admin/rentals` | admin | What is out right now, and the full history. Force-return button. |
| `/admin/trash` | admin | Trashed items: restore or delete permanently |
| `/admin/users`, `/admin/users/<id>/edit` | admin | User profiles (incl. new card number), and promoting/demoting admins |
| `/admin/labels` | admin | Printable QR label sheet for items and containers |
| `/admin/data` | admin | Export download, import upload (merge/replace), backups list and "backup now" |

---

## Data model (draft)

**User**: `id`, `card_number` (unique, 6 digits), `name` (optional), `email` (required),
`study_number` (8 digits, required), `is_admin`, `created_at`

**Category**: `id`, `name` (unique)

**SpecField**: `id`, `category_id`, `name` (unique within the category), `kind` (choice,
number or text), `unit` (numbers only), `position` (order on forms and in lists)

**SpecOption**: `id`, `field_id`, `label` (unique within the field)

**Product**: `id`, `name` (unique, e.g. "Basler ace"), `category_id` (optional),
`description`, `length_mm`, `width_mm`, `height_mm`, `created_at`, `updated_at`

**SpecValue**: `product_id` + `field_id` (together the key), and one of `option_id`,
`number` or `text`. No row means unknown.

**Item**: `id`, `code` (unique, random, never changes, no prefix), `product_id`,
`number` (automatic, unique together with the product), `container_id` (optional,
unique: one item per container), `created_at`, `updated_at`, `deleted_at`
(set when the item is in the trash, otherwise empty)

**Container**: `id`, `code` (unique, random, never changes, no prefix), `name`
(readable location, e.g. "Shelf B3, box 05"), `description`, `created_at`, `updated_at`

**Rental**: `id`, `item_id`, `user_id`, `rented_at`, `returned_at`, `returned_by_id`
(the admin who force-returned it, otherwise empty)
- An item is "rented" when it has a rental with no `returned_at`. This is computed, so
  there is no separate flag that can get out of sync.
- A return is only allowed by the user on the open rental, after scanning the item's
  container if it has one, or by an admin (force-return, no container scan).
- Deleting an item permanently also deletes its rentals and comments.

**Comment**: `id`, `item_id`, `user_id`, `text`, `created_at`
- Shown on the item page. Admins can delete comments. That's all.

All timestamps are stored in UTC and shown in Danish time.

---

## Export / import format

- Use **JSON** with a `schema_version` field (currently 2). Flat lists of users,
  containers, categories (with their spec fields and options), products (with their
  spec values by field name), items, rentals and comments. It's readable and works well
  with `git diff`.
- Version 1 files (from before products) can still be imported: items with the same
  name become copies of one product.
- `flask export data.json` and `flask import data.json --mode merge|replace`, plus
  download and upload on `/admin/data`.
- Import has two modes:
  - **replace**: wipe the database and load the file.
  - **merge**: insert or update rows, matching items by `code`, users by
    `card_number`, containers by `code`, and products and categories by name.
- References between records use those natural keys, not database IDs, so merging
  works across machines. Rentals are matched by item + `rented_at`, comments by
  item + user + time + text, so merging the same file twice adds nothing.
- An import is all-or-nothing, and is refused if it would leave no admins.

## Backups

- Reuse the export: write a dated JSON file to `data/backups/` once a day and keep the
  last 30.
- Run it as a small extra service in `docker-compose.yml` that sleeps in a loop and
  calls `flask backup`. That avoids the two gunicorn workers both running it.

---

## Open ideas (not decided)

- [ ] **Non-AAU users**, who would identify by email instead of a card
- [ ] **Due dates and an overdue list** for admins
- [ ] **Item photos**, uploaded by admins
- [ ] **Sort and filter by dimensions**, plus a CSV export for planning containers
- [ ] **Kits.** Rent a group of items with one scan (e.g. "Camera kit A")
- [ ] **Admin password** as a second step for admin pages
- [ ] **Browser tests in the repo**: the fake-camera Playwright test used during
      Phase 4 could become `tests/e2e/` (needs Playwright + Chrome, so kept optional)
- [ ] **Proper TLS certificate** from AAU IT. Phones warn about self-signed
      certificates, and the in-browser camera requires HTTPS.

---

## Phases

### Phase 0: Decisions
- [x] Scanning approach, return rule, user profile, item name, no data migration
- [x] Admin roles, containers, internet, branch
- [x] Admin login (card only), one item per container, items without a container

### Phase 1: Skeleton
- [x] On `dev`: delete the old code and create the new project layout (app factory,
      config, blueprints)
- [x] SQLAlchemy models + Alembic initial migration
- [x] Base template, CSS and navigation (vendored htmx and CSS, no CDN)
- [x] pytest setup + first test
- [x] New Dockerfile, compose and README (image build not yet tested: no Docker
      access on the dev machine; the start command was tested locally)

### Phase 2: Admin and inventory
- [x] `flask make-admin <email>` CLI command (promotes the first admin on the server)
- [x] Admin-only access check on `/admin/*`
- [x] Item list with search, filter by category and container, and sort by dimensions
- [x] Create and edit items
- [x] Create and edit containers, and assign/unassign items at any time
- [x] Trash: move items to the trash, restore them, delete them permanently (a
      rented item can't be trashed)
- [x] "Add N copies" helper for identical items (Basler ace #1–#15)
- [x] User list, and promoting/demoting admins (not yourself)

### Phase 3: Labels
- [x] Code generator (random, unique, never changes)
- [x] QR generation with the `VAP-` and `BOX-` prefixes (regular QR version 1, never
      Micro QR, which phone scanners can't read)
- [x] Printable sheet of small QR stickers, with the code in plain text so it can be
      typed by hand. Select which items or containers to print.
- [ ] Match the sticker size to the actual sticker paper (`--sticker-width` and
      `--qr-size` in `labels_print.html`) once it's chosen

### Phase 4: Users, renting and returning
- [x] Card scan → identify → register on first visit (store email lowercased; it's
      unique and `make-admin` looks it up)
- [x] Remember the user in a session cookie, with a "not you?" logout
- [x] `/rent`: scan several items, then confirm. Reject labels without a
      known prefix, and allow typing a code by hand.
- [x] `/return`: scan item → show its container → scan container → returned
      only if it matches. No container → returned straight away.
- [x] `/i/<code>` item page with a Rent button
- [x] Rules: no double rental, only the renter can return, right container required,
      clear errors for unknown codes, a multi-item rent succeeds fully or not at all
- [x] `/me` page listing my rentals
- [x] Admin view of what is out right now, and the history
- [x] Admin force-return
- [x] Tests for the rental rules
- [x] Browser test with a fake camera (card, item and container codes shown to Chrome):
      register, rent, type a code, return with container, sign out and in. Kept
      outside the repo for now; see Open ideas.

### Phase 5: Comments
- [x] Add a note on the item page, and optionally right after a return
- [x] Admins can delete notes, and see who wrote them

### Phase 6: Export, import and backup
- [x] JSON export (CLI + download)
- [x] JSON import with replace and merge modes (CLI + upload)
- [x] Round-trip test: export → import into an empty DB → identical data
- [x] Daily backup service with 30-day retention (`backup` service in compose; the
      newest 30 files are kept, and backups can be downloaded from `/admin/data`)

### Phase 8: Products, specs and filters
- [x] Split items into products (shared details) and items (physical copies); migration
      groups existing items by name
- [x] Categories as records, with spec fields (choice, number, text) defined by admins
- [x] Spec inputs on the product form, swapped in when the category changes
- [x] Public item list: one row per product, category tabs, spec filters in the URL,
      "only available now", note about products with unknown specs
- [x] Product page, and specs on the item page
- [x] Export/import schema version 2 (version 1 files still import)
- [x] Migrations run with SQLite foreign keys off, so rebuilding a table can't
      cascade-delete rentals and notes (found while testing this migration)
- [ ] Fill in the specs for all products, from the data sheets

### Phase 7: Deploy
- [ ] Deploy to the AAU server
- [ ] Register all items and print labels
- [ ] Put up the locker QR code that links to `/`

---

## Open questions

None right now. Answered questions are in "Decisions made".
