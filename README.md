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

[docker]: https://www.docker.com/
[api]: https://github.com/pdl-lex/pdl-api
[fastapi]: https://fastapi.tiangolo.com/
[frontend]: https://github.com/pdl-lex/pdl-platform
[vite]: https://vite.dev/
