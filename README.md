# ADL Platform Deployment

Docker setup for the LexoTerm German dictionary platform.

## Environment Variables

The following environment variables must be set:

```sh
MONGO_INITDB_ROOT_USERNAME
MONGO_INITDB_ROOT_PASSWORD
MONGODB_URI

POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB

PGADMIN_DEFAULT_EMAIL
PGADMIN_DEFAULT_PASSWORD

VITE_VM_URL

BASIC_AUTH_PASSWORD
```

## Deploying

To deploy the app after pushing changes to the api and/or the frontend,

1. wait for Github CI/CD to complete
2. `ssh` into the VM
3. `cd` into /home/deploy/adl-deployment
4. `git pull` the latest configuration.

Then, run the following commands to fetch the new images and update the containers.

```sh
docker compose pull
docker compose up -d
```

## Misc

The Caddy config can be modified and reloaded without restarting the service. From within the
repo folder /home/deploy/adl-deployment, you may edit conf/Caddyfile and execute the following
command to apply it:

```sh
docker compose exec -w /etc/caddy caddy caddy reload
```

Remember to update this repo whenever you modify the setup by committing and pushing your changes.
