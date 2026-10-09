# Apache Gluten Website

This repository contains the content for https://gluten.apache.org/.

## Documentation sync

The documentation under `_docs/` is synced automatically from the `docs/`
directory of [apache/incubator-gluten](https://github.com/apache/incubator-gluten)
by the [`sync_docs` workflow](.github/workflows/sync_docs.yml):

- `_docs/latest/` is refreshed daily from the `main` branch. Do not edit these
  files here; change them in the main repository instead.
- Release archives (`_docs/vX.Y.Z/`) are generated on demand: run the workflow
  manually from the Actions tab with `source_ref` set to the release tag and
  `version` set to `vX.Y.Z`.

The transformation (front matter rewriting for the just-the-docs navigation)
is implemented in [`scripts/sync_docs.py`](scripts/sync_docs.py), which can
also be run locally:

```bash
python3 scripts/sync_docs.py --source ../incubator-gluten/docs --dest _docs/latest --version latest
```

## Local development

```bash
bundle install
bundle exec jekyll serve
```
