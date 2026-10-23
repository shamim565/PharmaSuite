#!/usr/bin/env bash
# One-time GitHub repository metadata setup.
#
#   brew install gh
#   gh auth login
#   ./scripts/setup-github-metadata.sh
#
# The social preview and pinned repositories are web-UI only; this script prints
# the remaining manual steps at the end.

set -euo pipefail

REPO="${REPO:-shamim565/PharmaSuite}"
DESCRIPTION="Multi-branch medicine distribution ERP — atomic stock and ledger postings, FEFO inventory, branch-scoped RBAC, and audit trails. Django + DRF + Next.js."

if ! command -v gh >/dev/null 2>&1; then
  echo "gh is not installed. Run: brew install gh"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "You are not signed in to GitHub. Run: gh auth login"
  exit 1
fi

gh repo edit "$REPO" \
  --description "$DESCRIPTION" \
  --add-topic django \
  --add-topic drf \
  --add-topic erp \
  --add-topic inventory-management \
  --add-topic postgresql \
  --add-topic celery \
  --add-topic rbac \
  --add-topic nextjs \
  --add-topic typescript \
  --add-topic audit-log \
  --add-topic pharmacy \
  --add-topic distribution

echo
echo "Description and topics updated for $REPO."
echo
echo "Remaining steps (GitHub web UI only):"
echo "  1. Repo -> Settings -> General -> Social preview: upload a 1280x640 image."
echo "  2. Profile -> Customize your pins: pin PharmaSuite first, then five others."
echo "  3. Create <owner>/<owner>/README.md with a short profile and project links."
echo "  4. Add the live demo URL only after the API health check returns HTTP 200."
