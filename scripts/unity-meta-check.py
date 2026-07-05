#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


NATIVE_BUNDLE_SUFFIXES = (
    ".app",
    ".bundle",
    ".framework",
    ".plugin",
    ".xcframework",
)


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def annotation(kind: str, message: str, file: Path | None = None) -> None:
    if file is None:
        print(f"::{kind}::{message}")
    else:
        print(f"::{kind} file={file.as_posix()}::{message}")


def is_native_bundle_name(name: str) -> bool:
    lower = name.lower()
    return any(lower.endswith(suffix) for suffix in NATIVE_BUNDLE_SUFFIXES)


def should_ignore_relative_path(
    relative_path: Path,
    *,
    ignore_dotfiles: bool,
    ignore_tilde_paths: bool,
    ignore_native_bundle_contents: bool,
) -> bool:
    parts = relative_path.parts

    if ignore_dotfiles and any(part.startswith(".") for part in parts):
        return True

    if ignore_tilde_paths and any(part.endswith("~") for part in parts):
        return True

    if ignore_native_bundle_contents:
        for ancestor in parts[:-1]:
            if is_native_bundle_name(ancestor):
                return True

    return False


def target_for_meta(meta_path: Path) -> Path:
    return Path(str(meta_path)[:-5])


def check_tree(
    root: Path,
    *,
    project_root: Path,
    ignore_dotfiles: bool,
    ignore_tilde_paths: bool,
    ignore_native_bundle_contents: bool,
) -> tuple[int, int]:
    checked = 0
    errors = 0

    for path in sorted(root.rglob("*")):
        relative_to_root = path.relative_to(root)

        if path.name.endswith(".meta"):
            target = target_for_meta(path)
            target_relative = target.relative_to(root)
            if should_ignore_relative_path(
                target_relative,
                ignore_dotfiles=ignore_dotfiles,
                ignore_tilde_paths=ignore_tilde_paths,
                ignore_native_bundle_contents=ignore_native_bundle_contents,
            ):
                continue
            checked += 1
            if not target.exists():
                errors += 1
                annotation(
                    "error",
                    f"Orphan meta file: {path.relative_to(project_root).as_posix()}",
                    path.relative_to(project_root),
                )
            continue

        if should_ignore_relative_path(
            relative_to_root,
            ignore_dotfiles=ignore_dotfiles,
            ignore_tilde_paths=ignore_tilde_paths,
            ignore_native_bundle_contents=ignore_native_bundle_contents,
        ):
            continue

        checked += 1
        meta_path = Path(str(path) + ".meta")
        if not meta_path.exists():
            errors += 1
            annotation(
                "error",
                f"Missing meta file: {meta_path.relative_to(project_root).as_posix()}",
                path.relative_to(project_root),
            )

    return checked, errors


def package_roots(packages_scope: Path) -> list[Path]:
    if not packages_scope.is_dir():
        return []

    roots: list[Path] = []
    for child in sorted(packages_scope.iterdir()):
        if child.is_dir() and (child / "package.json").is_file():
            roots.append(child)
    return roots


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Unity .meta file consistency.")
    parser.add_argument("--path", default=".", help="Repository-relative Unity project path.")
    parser.add_argument("--scopes", default="Assets,Packages", help="Comma-separated project-relative roots to scan.")
    parser.add_argument("--ignore-dotfiles", type=parse_bool, default=True)
    parser.add_argument("--ignore-tilde-paths", type=parse_bool, default=True)
    parser.add_argument("--ignore-native-bundle-contents", type=parse_bool, default=True)
    parser.add_argument("--fail-on-empty", type=parse_bool, default=False)
    args = parser.parse_args()

    project_root = Path(args.path).resolve()
    if not project_root.is_dir():
        annotation("error", f"Project path does not exist or is not a directory: {args.path}")
        return 1

    total_checked = 0
    total_errors = 0

    for scope_name in split_csv(args.scopes):
        scope = project_root / scope_name
        if not scope.exists():
            annotation("notice", f"Skipping missing scope: {scope_name}")
            continue

        if scope.name == "Packages":
            roots = package_roots(scope)
            if not roots:
                annotation("notice", f"No embedded package roots found in scope: {scope_name}")
            for root in roots:
                checked, errors = check_tree(
                    root,
                    project_root=project_root,
                    ignore_dotfiles=args.ignore_dotfiles,
                    ignore_tilde_paths=args.ignore_tilde_paths,
                    ignore_native_bundle_contents=args.ignore_native_bundle_contents,
                )
                total_checked += checked
                total_errors += errors
            continue

        if not scope.is_dir():
            annotation("notice", f"Skipping non-directory scope: {scope_name}")
            continue

        checked, errors = check_tree(
            scope,
            project_root=project_root,
            ignore_dotfiles=args.ignore_dotfiles,
            ignore_tilde_paths=args.ignore_tilde_paths,
            ignore_native_bundle_contents=args.ignore_native_bundle_contents,
        )
        total_checked += checked
        total_errors += errors

    if total_checked == 0 and args.fail_on_empty:
        annotation("error", "No Unity assets or package files were checked.")
        total_errors += 1

    if total_errors:
        print(f"Unity meta check failed with {total_errors} issue(s).")
        return 1

    print(f"Unity meta check passed. Checked {total_checked} file/directory entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
