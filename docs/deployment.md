# Deployment

A fresh machine needs Docker with Compose.

```bash
git clone https://github.com/sohaib1khan/Ghostline.git
cd Ghostline
cp .env.example .env
```

Replace every `change-me` before the instance is reachable.

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put the first value in `APP_SECRET_KEY` and the second in `APP_ENCRYPTION_KEY`. Set `POSTGRES_PASSWORD` to a long random password. `DATABASE_URL` in `.env` is replaced by Compose with a URL that uses that password.

Then:

```bash
# .env
APP_ENV=production
APP_BASE_URL=https://learn.example.com
WEB_PORT=8080
```

`APP_BASE_URL` is the address people type. Approval mail uses it. The API refuses to start in production when a secret is missing, short, or still an example.

```bash
docker compose up -d --build
```

### First admin

**Automated:** set `BOOTSTRAP_ALLOW=true` plus `BOOTSTRAP_ADMIN_EMAIL` and a strong `BOOTSTRAP_ADMIN_PASSWORD` in `.env` before the first start. Logs show `GHOSTLINE BOOTSTRAP: admin ready for …`. Clear `BOOTSTRAP_ALLOW` and the password after you can sign in.

**Interactive:** leave bootstrap off, then:

```bash
docker compose logs backend | grep "GHOSTLINE SETUP TOKEN"
```

Open the site, complete `/setup` with that token, and keep the token out of chat logs and tickets. After the admin exists, a restart does not print a new token.

Health check: `https://learn.example.com/api/health` returns `{"status":"ok"}`.

## HTTPS reverse proxy

Publish Ghostline on localhost and terminate TLS in front of it.

```text
internet → Caddy or nginx (443) → 127.0.0.1:8080 (Ghostline web)
```

`WEB_PORT=8080` can stay bound to localhost:

```yaml
# only if you edit the published port in an override file
ports:
  - "127.0.0.1:8080:8080"
```

The stock Compose file publishes `${WEB_PORT:-8080}` on all interfaces. On a host with a public address, bind it to localhost in an override or close it with a firewall, and let the proxy be the public listener.

Caddy example:

```caddy
learn.example.com {
  reverse_proxy 127.0.0.1:8080
  header {
    Strict-Transport-Security "max-age=31536000; includeSubDomains"
  }
}
```

nginx example:

```nginx
server {
  listen 443 ssl;
  server_name learn.example.com;
  # ssl_certificate and ssl_certificate_key go here.

  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

  location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
}
```

Set `APP_BASE_URL` to the `https://` address. The session cookie is marked Secure when `APP_ENV=production`, so sign-in requires HTTPS.

Do not add HSTS on the Ghostline container itself. That container also answers plain HTTP, and a browser that has seen HSTS will refuse the local address.

## Operations

- Postgres is not published. Use `docs/backup-restore.md`.
- Logs rotate at 10 MB, three files per service.
- Memory caps: database 512 MB, API 768 MB, web 256 MB.
- `docker compose ps` should show all three services healthy.
- Image scans run in CI with Trivy. A high or critical finding that has a fix fails the workflow.

## Upgrades

```bash
git pull
docker compose up -d --build
```

The API applies database migrations as it starts. Take a backup before an upgrade.
