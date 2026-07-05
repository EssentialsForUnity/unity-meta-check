#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
valid_fixture="$repo_root/tests/fixtures/valid-unity-project"
tmp_root="$(mktemp -d)"
last_output=""

trap 'rm -rf "$tmp_root"' EXIT

expect_failure() {
  local name="$1"
  shift

  local output="$tmp_root/${name}.txt"
  set +e
  "$@" >"$output" 2>&1
  local status=$?
  set -e

  cat "$output"

  if [[ "$status" -eq 0 ]]; then
    echo "Expected $name to fail."
    exit 1
  fi

  last_output="$output"
}

expect_output() {
  local pattern="$1"

  if ! grep -Fq "$pattern" "$last_output"; then
    echo "Expected output to contain: $pattern"
    exit 1
  fi
}

copy_valid_fixture() {
  local destination="$1"
  cp -R "$valid_fixture" "$destination"
}

checker=(python3 "$repo_root/scripts/unity-meta-check.py")

expect_failure invalid-fixture \
  "${checker[@]}" --path "$repo_root/tests/fixtures/invalid-unity-project"
expect_output "Missing meta file: Assets/Missing.txt.meta"
expect_output "Orphan meta file: Assets/Orphan.txt.meta"

missing_asset_meta="$tmp_root/missing-asset-meta"
copy_valid_fixture "$missing_asset_meta"
rm "$missing_asset_meta/Assets/Scenes/Main.unity.meta"
expect_failure missing-asset-meta \
  "${checker[@]}" --path "$missing_asset_meta"
expect_output "Missing meta file: Assets/Scenes/Main.unity.meta"

orphan_asset_meta="$tmp_root/orphan-asset-meta"
copy_valid_fixture "$orphan_asset_meta"
rm "$orphan_asset_meta/Assets/Scenes/Main.unity"
expect_failure orphan-asset-meta \
  "${checker[@]}" --path "$orphan_asset_meta"
expect_output "Orphan meta file: Assets/Scenes/Main.unity.meta"

missing_package_meta="$tmp_root/missing-package-meta"
copy_valid_fixture "$missing_package_meta"
rm "$missing_package_meta/Packages/com.example.fixture/Runtime/Foo.cs.meta"
expect_failure missing-package-meta \
  "${checker[@]}" --path "$missing_package_meta"
expect_output "Missing meta file: Packages/com.example.fixture/Runtime/Foo.cs.meta"

orphan_package_meta="$tmp_root/orphan-package-meta"
copy_valid_fixture "$orphan_package_meta"
rm "$orphan_package_meta/Packages/com.example.fixture/Runtime/Foo.cs"
expect_failure orphan-package-meta \
  "${checker[@]}" --path "$orphan_package_meta"
expect_output "Orphan meta file: Packages/com.example.fixture/Runtime/Foo.cs.meta"

empty_project="$tmp_root/empty"
mkdir -p "$empty_project/Assets"
expect_failure empty-required-scan \
  "${checker[@]}" --path "$empty_project" --fail-on-empty true
expect_output "No Unity assets or package files were checked."
