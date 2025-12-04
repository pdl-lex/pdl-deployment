# LexoTerm Digital Infrastructure

Contains configuration and infrastructure setup for the *LexoTerm* dictionary platform deployment.

The infrastructure is distributed in [Docker][docker] containers managed via `docker compose`. Its
main components are:

1. A Python [api][api] powered by [FastAPI][fastapi]
2. A lexicographic [research application][frontend] based on TypeScript/React and [Vite][vite]
3. One or more databases holding dictionaries and corpora
4. Importers for converting, validating and storing input data in the databases
5. [Caddy][caddy] reverse proxy to manage access and SSL

![Infrastructure diagram created with eraser.io](img/infrastructure.svg)

## Deploying

To deploy the app after pushing changes to the api and/or the frontend,

1. wait for Github CI/CD to complete
2. `ssh` into the VM
3. switch to the deploy user with `su - deploy` (enter password)
4. `cd` into ~/adl-deployment
5. `git switch main && git pull` to update to the latest configuration.

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
