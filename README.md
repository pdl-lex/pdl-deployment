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
   directory – if you plan to migrate them to the new location, see, e.g., [this post][so-docker] on Stackoverflow.
3. Install [Dokploy](https://dokploy.com/).

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

## Adding Services in Dokploy

There are different options to add services in the Dokploy UI, depending on what kind of service
you'd like to set up. (tba)

[docker]: https://www.docker.com/
[api]: https://github.com/pdl-lex/pdl-api
[fastapi]: https://fastapi.tiangolo.com/
[frontend]: https://github.com/pdl-lex/pdl-platform
[vite]: https://vite.dev/
[lrz-docs]: https://doku.lrz.de/faqs-zu-virtuellen-maschinen-am-lrz-10745762.html
[so-docker]: https://stackoverflow.com/questions/59345566/move-docker-volume-to-different-partition
[lrz-dns]: https://doku.lrz.de/dns-service-10333170.html#DNSService-Webdns-EinträgeinLRZ-NameserverüberWebinterface
