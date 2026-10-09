#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Sync docs from the apache/incubator-gluten repository into _docs/<version>.

Takes a checkout of gluten's docs/ directory and rewrites the just-the-docs
front matter so the whole tree hangs under a single version entry in the
site navigation:

  docs/index.md                    -> version root page
  section indexes (has_children)   -> parent: <version root>
  section child pages              -> grand_parent: <version root>
  top-level velox-*.md pages       -> grouped under a generated "Velox Backend"
                                      section (front matter only, files keep
                                      their location so relative links work)
  other top-level pages            -> parent: <version root>
  pages without front matter       -> front matter injected, attached to the
                                      section owning their directory

Usage:
  python3 scripts/sync_docs.py --source ../gluten/docs --dest _docs/latest --version latest
  python3 scripts/sync_docs.py --source ../gluten/docs --dest _docs/v1.6.0 --version v1.6.0
"""

import argparse
import os
import re
import shutil
import sys

EXCLUDED = {"_config.yml"}
VELOX_GROUP_TITLE = "Velox Backend"


def parse_pairs(block):
    pairs = []
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*?)\s*$", line)
        if m:
            pairs.append([m.group(1), m.group(2)])
    return pairs


def parse_front_matter(text):
    """Return (list of (key, value) pairs, body) or (None, text) if no front matter."""
    if text.startswith("---"):
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
        if match:
            return parse_pairs(match.group(1)), text[match.end():]
        return None, text
    # Some generated files (e.g. Configuration.md) carry a malformed
    # front-matter-like block after a leading HTML comment. Jekyll ignores it
    # and renders it as literal text; absorb its keys and drop it from the body.
    match = re.match(r"^(\s*<!--.*?-->\s*\n)\s*-{3,}\s*\n(.*?)\n\s*-{3,}\s*\n",
                     text, re.DOTALL)
    if match and "title:" in match.group(2):
        return parse_pairs(match.group(2)), match.group(1) + text[match.end():]
    return None, text


def fm_get(pairs, key):
    for k, v in pairs:
        if k == key:
            return v
    return None


def fm_set(pairs, key, value):
    for pair in pairs:
        if pair[0] == key:
            pair[1] = value
            return
    pairs.append([key, value])


def render(pairs, body):
    lines = ["---"] + ["%s: %s" % (k, v) for k, v in pairs] + ["---", ""]
    return "\n".join(lines) + body


def title_from_filename(name):
    words = re.sub(r"\.md$", "", name).replace("-", " ").replace("_", " ").split()
    return " ".join(w if w[:1].isupper() else w.capitalize() for w in words)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="path to gluten docs/ directory")
    parser.add_argument("--dest", required=True, help="target directory, e.g. _docs/latest")
    parser.add_argument("--version", required=True, help="version label, e.g. latest or v1.6.0")
    args = parser.parse_args()

    is_latest = args.version == "latest"
    root_title = "Documentation (Latest)" if is_latest else args.version
    url_prefix = "/docs/latest" if is_latest else "/archives/%s" % args.version

    if not os.path.isdir(args.source):
        sys.exit("source directory not found: %s" % args.source)

    # Fresh copy of the whole tree (images, configs, notebooks included).
    if os.path.isdir(args.dest):
        shutil.rmtree(args.dest)
    shutil.copytree(args.source, args.dest,
                    ignore=lambda d, names: [n for n in names if n in EXCLUDED])

    md_files = []
    for cur, _dirs, names in os.walk(args.dest):
        for name in names:
            if name.endswith(".md"):
                md_files.append(os.path.join(cur, name))

    # Map each directory to the title of its section index (has_children, no parent).
    section_title_by_dir = {}
    for path in md_files:
        text = open(path, encoding="utf-8").read()
        pairs, _body = parse_front_matter(text)
        if pairs is None:
            continue
        if fm_get(pairs, "has_children") == "true" and not fm_get(pairs, "parent"):
            if os.path.relpath(path, args.dest) != "index.md":
                section_title_by_dir[os.path.dirname(path)] = fm_get(pairs, "title")

    has_velox_group = False

    for path in md_files:
        rel = os.path.relpath(path, args.dest)
        in_root = os.path.dirname(rel) == ""
        text = open(path, encoding="utf-8").read()
        pairs, body = parse_front_matter(text)

        if rel == "index.md":
            pairs = [["layout", "page"], ["title", root_title], ["nav_order", "1"],
                     ["has_children", "true"], ["permalink", url_prefix + "/"]]
            if not is_latest:
                pairs.insert(4, ["parent", "Archives"])
            open(path, "w", encoding="utf-8").write(render(pairs, body))
            continue

        if pairs is None:
            pairs = [["layout", "page"],
                     ["title", title_from_filename(os.path.basename(rel))]]

        parent = fm_get(pairs, "parent")
        if parent:
            # Some pages carry a stale or path-like parent (e.g. "Getting-Started"
            # vs the section title "Getting Started", or "/developer-overview/");
            # normalize it to the owning directory's section title.
            section = section_title_by_dir.get(os.path.dirname(path))
            if section and parent not in section_title_by_dir.values():
                fm_set(pairs, "parent", section)
            fm_set(pairs, "grand_parent", root_title)
        elif fm_get(pairs, "has_children") == "true":
            fm_set(pairs, "parent", root_title)
        elif in_root and os.path.basename(rel).startswith("velox-"):
            fm_set(pairs, "parent", VELOX_GROUP_TITLE)
            fm_set(pairs, "grand_parent", root_title)
            has_velox_group = True
        elif in_root:
            fm_set(pairs, "parent", root_title)
        else:
            section = section_title_by_dir.get(os.path.dirname(path))
            if section:
                fm_set(pairs, "parent", section)
                fm_set(pairs, "grand_parent", root_title)
            else:
                fm_set(pairs, "parent", root_title)

        permalink = fm_get(pairs, "permalink")
        if permalink:
            fm_set(pairs, "permalink", url_prefix + "/" + permalink.strip("/") + "/")

        open(path, "w", encoding="utf-8").write(render(pairs, body))

    if has_velox_group:
        index = render([["layout", "page"], ["title", VELOX_GROUP_TITLE],
                        ["nav_order", "4"], ["has_children", "true"],
                        ["parent", root_title],
                        ["permalink", url_prefix + "/velox-backend/"]],
                       "# Velox backend documents\n")
        open(os.path.join(args.dest, "velox-backend.md"), "w", encoding="utf-8").write(index)

    print("Synced %s -> %s (version: %s)" % (args.source, args.dest, args.version))


if __name__ == "__main__":
    main()
