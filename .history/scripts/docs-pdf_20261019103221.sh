#!/usr/bin/env bash
# Turn the submission documents (docs/*.md) into PDFs in docs/pdf/.
#   scripts/docs-pdf.sh technical-documentation security-self-assessment test-report
# Needs pandoc and the Playwright Chromium the client already uses.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p docs/pdf
for name in "$@"; do
  pandoc "docs/$name.md" --standalone --embed-resources --css scripts/docs-pdf.css \
    --resource-path=docs --metadata pagetitle="$name" -o "docs/pdf/$name.html"
  (cd client && node scripts/print-pdf.mjs "../docs/pdf/$name.html" "../docs/pdf/$name.pdf")
  rm "docs/pdf/$name.html"
  echo "wrote docs/pdf/$name.pdf"
done
