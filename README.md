# wikiHow Scraper

A tool for downloading, incrementally updating, parsing, 
and rendering wikiHow procedural articles.

## Quick Start

### Step 1: Create the environment

Run from the `wikihow/` root:

```bash
python3 -m venv venv-wikihow
source venv-wikihow/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
````

### Step 2: Fetch a page

```bash
python src/main.py fetch https://www.wikihow.com/Bake-Brie
```

Downloaded HTML and metadata go to:

```text
out/html/
```

### Step 3: Parse downloaded pages

```bash
python src/main.py parse
```

Outputs:

```text
out/
├── html/   Raw HTML + .meta.json sidecars
├── json/   Structured article records
└── md/     Human-readable Markdown
```

## Commands

### 1. `fetch`

Fetch one or more wikiHow pages:

```bash
python src/main.py fetch <url> [<url> ...]
python src/main.py fetch --from-file urls.txt
```

Main options:

| Option        | Default    | Meaning                          |
| ------------- | ---------- | -------------------------------- |
| `--from-file` | none       | one URL per line                 |
| `--delay`     | `3.0`      | delay after each network attempt |
| `--cache-dir` | `out/html` | HTML archive directory           |

The scraper checks `robots.txt`, skips cached pages, and stores a `.meta.json` sidecar containing:

```text
url
requested_url
retrieved_utc
sha256
status
robots
```

### 2. `parse`

Parse archived HTML into JSON and Markdown:

```bash
python src/main.py parse
```

Each archived page is checked against its recorded SHA-256 before parsing. If the file has changed since download, it is skipped rather than silently parsed.

### 3. `update`

Incrementally update the corpus from the wikiHow sitemap.

* Preview first:

  ```bash
  python src/main.py update --tokens bake,boil --dry-run
  ```

* Fetch selected pages:

  ```bash
  python src/main.py update --tokens bake,boil
  ```

* Limit one run:

  ```bash
  python src/main.py update --tokens bake,boil --limit 50
  ```

* Fetch the full sitemap:

  ```bash
  python src/main.py update --all
  ```

  There are roughly 62,000 pages. One should never do anything at scale merely because an option permits it.

| Option      | Meaning                                               |
| ----------- | ----------------------------------------------------- |
| `--tokens`  | exact comma-separated words matched against URL slugs |
| `--all`     | select the full sitemap                               |
| `--limit`   | maximum pages fetched this run                        |
| `--dry-run` | preview without changing data                         |
| `--state`   | sitemap snapshot path                                 |

For example:

```text
https://www.wikihow.com/Bake-Brie
```

contains the tokens:

```text
bake
brie
```

So:

```bash
python src/main.py update --tokens bake
```

matches it.

Token matching is exact. `boil` matches `Boil-Water`, but not `Boiling-Water`.

## Output

```text
out/
├── html/
│   ├── <slug>.html
│   └── <slug>.meta.json
├── json/
│   └── <slug>.json
└── md/
    └── <slug>.md

state/
└── sitemap.json
```

Each parsed step preserves wikiHow's procedural structure:

```json
{
  "sid": "m1s1",
  "ordinal": 1,
  "instruction": "Place the pot on the stove.",
  "elaboration": "Use high heat until the water boils.",
  "details": [
    "Covering the pot can reduce heating time."
  ]
}
```

`sid` means step ID. For example, `m1s1` means Method 1, Step 1.

