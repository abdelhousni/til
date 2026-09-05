# Publishing a TIL collection as a static GitHub Pages site

I forked [simonw/til](https://github.com/simonw/til) to start my own "Today I Learned" collection, but its publishing pipeline was built around Simon's own infrastructure: `build_database.py` compiled every entry into a sqlite database, `generate_screenshots.py` rendered preview images via Playwright, and the GitHub Actions workflow pushed the result to an S3 bucket and deployed a Datasette instance on Fly.io. None of that infrastructure was mine, so the workflow just failed without those secrets configured.

Since I only wanted a browsable index of my own notes, I replaced the whole pipeline with a much smaller one:

- `update_readme.py` scans the topic directories directly and rewrites the README's index between `<!-- index starts -->` / `<!-- index ends -->` markers. Instead of reading dates from a database, it shells out to `git log --follow --diff-filter=A --date=short` per file to find when it was actually added.
- `build_site.py` converts every `topic/entry.md` into a standalone HTML page (via the `markdown` package) plus one `index.html` grouping everything by topic, and writes it all to `_site/`.
- `.github/workflows/publish.yml` runs both scripts on every push to `main`, commits the refreshed README if it changed, then uploads `_site/` with `actions/upload-pages-artifact` and deploys it with `actions/deploy-pages`.

That last part is a pattern Simon documented himself, in his own TIL: [github-actions/github-pages.md](https://github.com/simonw/til/blob/main/github-actions/github-pages.md). The minimal recipe is just:

```yaml
permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - run: |
        mkdir _site
        echo '<h1>Hello, world!</h1>' > _site/index.html
    - uses: actions/upload-pages-artifact@v3
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

Anything written into `_site/` before the `upload-pages-artifact` step gets published. The three permissions are all required: `contents: read` for checkout, `pages: write` to publish, and `id-token: write` because `deploy-pages` needs it to authenticate.

One gotcha I hit: my repo has a topic folder literally named `markdown/`, which shadowed the pip `markdown` package the build script imports — Python adds the script's own directory to `sys.path`, so `import markdown` found the empty local folder instead of the real library. Fixed by stripping the script's directory from `sys.path` before importing it.

Enabling Pages with "build from GitHub Actions" as the source (rather than a branch) can be done from the repo settings UI, or via the API:

```bash
gh api -X POST repos/OWNER/REPO/pages -f 'build_type=workflow'
```

The site now lives at <https://abdelhousni.github.io/til/>, with no Fly, S3, or Datasette involved.
