#!/usr/bin/env bash
# _compute_sha.sh — regenerate expected sha256 values for the patch-system
# test fixtures. Not consumed at test time — run manually after editing any
# file under vendor-mini/ or vendor-mini-patched/ and update series.json +
# patches/*.patch X-*-Sha256 headers accordingly.
#
# Usage: tests/fixtures/_compute_sha.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${HERE}"

echo "# Pristine (vendor-mini/):"
find vendor-mini -type f | sort | while read -r f; do
    sha="$(sha256sum "$f" | awk '{print $1}')"
    printf "  %s  %s\n" "$sha" "$f"
done

echo
echo "# Patched (vendor-mini-patched/):"
find vendor-mini-patched -type f | sort | while read -r f; do
    sha="$(sha256sum "$f" | awk '{print $1}')"
    printf "  %s  %s\n" "$sha" "$f"
done
