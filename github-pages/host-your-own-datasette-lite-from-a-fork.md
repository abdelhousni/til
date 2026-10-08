# Hosting my own copy of Datasette Lite from a fork

[Datasette Lite](https://github.com/simonw/datasette-lite) is Simon Willison's build of [Datasette](https://datasette.io/) (a tool that publishes a SQLite database as a browsable, queryable website) that runs entirely in the browser. Simon explains how it works, Python compiled to WebAssembly via Pyodide inside a web worker, in [Datasette Lite: a server-side Python web application running in a browser](https://simonwillison.net/2022/May/4/datasette-lite/), and the [README](https://github.com/simonw/datasette-lite#readme) lists the `?url=`, `?csv=`, `?json=` and `?parquet=` parameters for loading data. I won't repeat any of that here. This entry is only about running my own copy, at <https://abdelhousni.github.io/datasette-lite/>.

## The whole site is static files

The repository root *is* the site: `index.html`, `app.css` and `webworker.js`, with no build step. So GitHub Pages (GitHub's free static hosting, see [publishing a static site](static-site-instead-of-datasette.md)) can serve it straight from a branch: fork the repo, then in **Settings → Pages** pick **Deploy from a branch**, `main`, `/ (root)`. No workflow needed; the fork's only workflow, `test.yml`, just runs the tests.

## Delete the inherited CNAME

The fork came with a `CNAME` file containing `lite.datasette.io`. GitHub Pages reads that file as "serve this site on this custom domain", so my fork tried to claim Simon's domain instead of using `abdelhousni.github.io/datasette-lite`. Deleting it (one commit, `build: Delete CNAME`) was the only change the fork needed. Any fork of a Pages site with a custom domain has the same trap.

## Keeping it current

Because my only change is that deletion, catching up with upstream is a fast "Sync fork" on GitHub, or a merge that never conflicts. When I checked in October 2026, my `main` already sat on upstream's tip, `779b2d4`, which added support for passing `?url=` more than once to load several databases at the same time.

Credit: everything that makes this work is Simon Willison's; this is just how to host a copy of it.

TODO: serve this copy under my own domain. This site's custom domain, `til.housni.eu`, belongs to the `til` project site only, so it doesn't cover `abdelhousni.github.io/datasette-lite`. Either add a redirect page at `til.housni.eu/datasette-lite/` that keeps the `?url=` parameters, or put a subdomain such as `lite.housni.eu` in the fork's `CNAME` file and point a DNS record at it.
