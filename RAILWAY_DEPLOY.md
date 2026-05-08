# Railway Deploy Notes

## 1. Services

Create two services inside the same Railway project:

- `web` service for the bot application
- `PostgreSQL` service for the database

Railway will expose `DATABASE_URL` from the PostgreSQL service to the web service once linked.

## 2. Start Command

Use this start command for the web service:

```bash
python server.py
```

## 3. Environment Variables

Required:

- `BOT_TOKEN`
- `DATABASE_URL`
- `APP_BASE_URL`

Telegram webhook:

- `TELEGRAM_WEBHOOK_PATH=/webhooks/telegram`
- `BOT_WEBHOOK_SECRET_TOKEN=<your telegram secret token>`

Gameplay / monetization:

- `MAX_PLAYERS_PER_GAME=10`
- `FREE_TRIAL_GAMES_PER_CHAT=3`

Stripe:

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`

Stripe price ids are stored in the `subscription_plans` database table and seeded by migrations.

Optional:

- `HOST=0.0.0.0`
- `PORT` is usually injected by Railway automatically
- `ADMIN_USER_ID` Telegram user id that acts as the super-admin in private bot chat and every other chat; system admin notifications are sent to this user's private bot chat
- `PERMISSION_TABLE_CACHE_TTL` cache lifetime for chat admin permissions as an ISO 8601 duration, for example `PT5M`, `PT1H`, or `P1D`. Defaults to `PT1H`.
- `CHAT_USAGE_WARNING_THRESHOLD` usage ratio for chat limit warnings, greater than `0` and up to `1`. Defaults to `0.8`.
- `ENABLED_FEATURES` comma-separated feature toggles to enable. Defaults to all guarded features: `revanche,savegroup,groups,analyze,history,export_csv,sub_refund`.

## 4. Database Migration

Run migrations before first production traffic:

```bash
python -m alembic upgrade head
```

If you use a Railway one-off shell, run the same command there.

## 5. Telegram Webhook

After deployment, configure Telegram to call:

```text
https://<your-app-domain>/webhooks/telegram
```

Use the same value as `BOT_WEBHOOK_SECRET_TOKEN` for Telegram's `secret_token`.

## 6. Stripe Webhook

Configure Stripe to call:

```text
https://<your-app-domain>/webhooks/stripe
```

Recommended subscribed events:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `charge.refunded`

The service also supports API refresh of subscription state, so delayed or out-of-order webhooks do not leave the local billing model stale.

## 7. Healthcheck

Railway can use:

```text
/healthz
```

## 8. Notes

- Current schema is managed through Alembic.
- Main deployment entrypoint for Railway is `server.py`.
- Product metrics are stored in the `product_metric_events` table.
- Saved regular companies are stored in `saved_groups` and `saved_group_members`.
