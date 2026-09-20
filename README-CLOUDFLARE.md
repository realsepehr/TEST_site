# Hafez — Cloudflare-native deployment

This version keeps the existing Flask/Jinja storefront and admin panel, but moves persistent state to Cloudflare:

- **D1** → products, categories, settings, analytics and admin activity
- **R2** → product images and gallery files
- **Workers + Python/Flask** → application runtime
- **Flask signed session cookie** → admin login session; `SECRET_KEY` is stored as a Worker secret

Cloudflare documents Flask support through its WSGI adapter and D1/R2 bindings for Python Workers. See the official docs linked below.

## 1. Create the resources

From the project folder:

```bash
npx wrangler login
npx wrangler d1 create hafez-store-db
npx wrangler r2 bucket create hafez-store-media
```

Take the `database_id` printed by the D1 command and put it in `wrangler.jsonc` in place of `PUT_YOUR_D1_DATABASE_ID_HERE`.

## 2. Initialize D1

```bash
npx wrangler d1 execute hafez-store-db --remote --file=./schema.sql
```

This creates the tables and default settings/categories.

## 3. Set admin secrets

```bash
npx wrangler secret put SECRET_KEY
npx wrangler secret put ADMIN_USERNAME
npx wrangler secret put ADMIN_PASSWORD
```

Optional:

```bash
npx wrangler secret put ADMIN_2FA_SECRET
```

For a custom domain, add it to `TRUSTED_HOSTS` if needed:

```bash
npx wrangler secret put TRUSTED_HOSTS
```

Example value:

```text
shop.example.com
```

## 4. Deploy

```bash
npx wrangler deploy
```

Do **not** deploy this as a static Cloudflare Pages site. It is a Python Worker running Flask.

## 5. Admin panel

The existing private admin path is preserved. The application also keeps `/hafez-panel` as a redirect to the secure admin entry flow.

Login credentials are no longer stored in the source code; they come from Worker secrets.

## 6. Images

New uploads from the admin panel are stored in R2 under `products/`. Product records store the R2 object key in `image` and `gallery`.

Images are served by `/media/<r2-key>` and cached with a long immutable cache lifetime.

## 7. Backups

`/admin/backup` downloads a JSON snapshot of D1 tables.

`/admin/backup/full` downloads a ZIP containing the D1 JSON snapshot and an R2 media manifest. The media objects remain in R2; the ZIP does not duplicate all image bytes.

For disaster recovery, keep D1's own backups/time-travel facilities enabled and retain the R2 bucket.

## Important

The old Railway-only `sitecustomize.py` persistence layer is disabled in this build. SQLite and local `static/uploads` remain only as a local-development fallback.
