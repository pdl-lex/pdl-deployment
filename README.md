# LexoTerm Digital Infrastructure

Contains configuration and infrastructure setup for [LexoTerm](https://lexoterm.de/) and other
lexicographic tools developed as part of
[Neue Potenziale für die digitale Lexikographie des Deutschen](https://pdl.badw.de/).

The infrastructure is distributed in [Docker][docker] containers managed via
[Dokploy](https://dokploy.com/). Its main components are:

1. A Python [api][api] powered by [FastAPI][fastapi]
2. A lexicographic [research application][frontend] based on TypeScript/React and [Vite][vite]
3. One or more databases holding dictionaries and corpora
4. Importers for converting, validating and storing input data in the databases

## Setup

1. Set up the server according to the [LRZ docs][lrz-docs] (set up users, ssh keys, etc.)
2. Install [Docker][docker]. If you set up a dedicated data partition as per LRZ recommendations,
   make sure to set `data-root` in /etc/docker/daemon.json to the correct location (something like
   /mnt/data/docker). Note that already existing images are not automatically moved to the new
   directory – if you plan to migrate them to the new location, see, e.g., [this post][so-docker]
   on Stackoverflow.
3. Install [Dokploy](https://dokploy.com/). In the UI, remember to move to the web server settings,
   add a custom domain (like `manage.your-domain.de` – cf. [DNS Management](#dns-management)).

## DNS Management

To make services available online, you may want to purchase a custom domain and add subdomains like
`api.your-domain.de`. Although you can also use paths like `your-domain.de/api`, many tools expect
to live at the root and may break things when put into a subpath, so subdomains is generally more
hassle-free.

Custom domains can be purchased by LRZ. They can also set up subdomains or give you access to the
DNS management NameSurfer so you can do it yourself (see the [LRZ docs on DNS management][lrz-dns]).

To add a subdomain in webdns.lrz.de, select your domain in the DNS tab and click *Add CNAME*
in the left sidebar. Put the desired prefix as name (e.g., `api` for `api.lexoterm.de`) and enter
the VM's URL as CNAME alias. Confirm with ok. (It may take a few minutes for the domain to become
active.)

## Adding Services

Before you can add services, create a new project in the Dokploy GUI if you haven't done so yet.

There are different options to add services in the Dokploy UI, depending on what kind of service
you'd like to set up. The preferred way seems to be adding services as applications (options 1 and
2 below) because that gives you the most features. In general, however, the procedure is mostly the
same: Create a new service, set up environment variables and the domain, and deploy.

A note on networks: Dokploy services automatically join the dokploy-network so they can talk to
each other by default.

### 1. Adding Published Images

Many of our services are pushed to GitHub Container Registry (GHCR) via CI/CD. Although Dokploy can
also build images (see below), pulling built images from GHCR is preferred because building can put
significant load on the server.

Since you need credentials but don't want to use your actual password here, you should set up a
[Github personal access token][pat] (PAT).

1. In your Dokploy project, click on *Create Service*, select *Application* and pick a name.
2. In the *General* tab, select Docker as provider. In the *Docker Image* field, paste your GHCR url
   (something like `ghcr.io/pdl-lex/your-repo-name/latest`). Use `ghcr.io` as registry url. Username
   is your GitHub username. For the password, paste your personal access token.
   **Do NOT use your personal password.** Click Save.
3. In the *Environment* tab, paste the contents of your .env. Make sure to name the variables
   *exactly* as they are required by the app – since we do not have an editable compose file
   here, we cannot rename variables (like `DATABASE_URL=${MONGODB_URI}`). Click Save.
4. In the *Domains* tab, click *Add Domain*. For the host, use your custom subdomain like
   `my-service.lexoterm.de` (cf. [DNS Management](#dns-management)). Configure the container port
   according to your application (mostly 3000 or 80 – check the Dockerfile in the source repo of the
   service). Enable HTTPS and select Let's Encrypt as certificate provider.
5. Back in the *General* tab, click *Deploy*. Wait for the service to build and the certificate to
   be rolled out (this may take a minute or so).

If the build fails, check the build log for errors. If the build works but the app doesn't work,
check the container logs: In Dokploy, navigate to the Docker tab, find your service, click on the
three dots and view logs.

### 2. GitHub Repositories containing a Dockerfile

TODO

### 3. Raw Compose

TODO

[docker]: https://www.docker.com/
[api]: https://github.com/pdl-lex/pdl-api
[fastapi]: https://fastapi.tiangolo.com/
[frontend]: https://github.com/pdl-lex/pdl-platform
[vite]: https://vite.dev/
[lrz-docs]: https://doku.lrz.de/faqs-zu-virtuellen-maschinen-am-lrz-10745762.html
[so-docker]: https://stackoverflow.com/questions/59345566/move-docker-volume-to-different-partition
[lrz-dns]: https://doku.lrz.de/dns-service-10333170.html#DNSService-Webdns-EinträgeinLRZ-NameserverüberWebinterface
[pat]: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
