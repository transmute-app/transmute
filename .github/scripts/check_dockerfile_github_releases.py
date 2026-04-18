#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


RELEASE_COMMENT_RE = re.compile(r"^\s*#\s*(https://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/releases/?(?:\s*)?)$")
ARG_RE = re.compile(r'^\s*ARG\s+(?P<name>[A-Z0-9_]+)="?(?P<value>[^"\s]+)"?\s*$')


@dataclass(frozen=True)
class DependencyRelease:
    arg_name: str
    current_version: str
    upstream_owner: str
    upstream_repo: str
    releases_url: str

    @property
    def upstream_full_name(self) -> str:
        return f"{self.upstream_owner}/{self.upstream_repo}"


@dataclass(frozen=True)
class LatestRelease:
    tag_name: str
    html_url: str


def normalize_version(value: str) -> str:
    value = value.strip()
    if value.startswith("refs/tags/"):
        value = value[len("refs/tags/") :]
    if value.startswith("v") and len(value) > 1 and value[1].isdigit():
        return value[1:]
    return value


def build_request(url: str, token: str | None = None, method: str = "GET", data: bytes | None = None) -> urllib.request.Request:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "transmute-dockerfile-release-checker",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url=url, headers=headers, method=method, data=data)


def github_json_request(url: str, token: str | None = None, method: str = "GET", payload: dict | None = None) -> dict | list:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = build_request(url=url, token=token, method=method, data=data)
    if data is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed: {method} {url} -> {exc.code} {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub API request failed: {method} {url} -> {exc.reason}") from exc


def parse_dockerfile(path: Path) -> list[DependencyRelease]:
    dependencies: list[DependencyRelease] = []
    pending_release_comment: tuple[str, str, str] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        release_match = RELEASE_COMMENT_RE.match(raw_line)
        if release_match:
            pending_release_comment = (
                release_match.group("owner"),
                release_match.group("repo"),
                release_match.group(1).strip(),
            )
            continue

        arg_match = ARG_RE.match(raw_line)
        if arg_match and pending_release_comment is not None:
            owner, repo, releases_url = pending_release_comment
            dependencies.append(
                DependencyRelease(
                    arg_name=arg_match.group("name"),
                    current_version=arg_match.group("value"),
                    upstream_owner=owner,
                    upstream_repo=repo,
                    releases_url=releases_url,
                )
            )
            pending_release_comment = None
            continue

        if raw_line.strip() and not raw_line.lstrip().startswith("#"):
            pending_release_comment = None

    return dependencies


def get_latest_release(owner: str, repo: str, token: str | None) -> LatestRelease:
    latest_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        release = github_json_request(latest_url, token=token)
    except RuntimeError as exc:
        if " 404 " not in str(exc):
            raise
        releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=10"
        releases = github_json_request(releases_url, token=token)
        if not isinstance(releases, list):
            raise RuntimeError(f"Unexpected releases payload for {owner}/{repo}")
        release = next((item for item in releases if not item.get("draft") and not item.get("prerelease")), None)
        if release is None:
            raise RuntimeError(f"No non-draft release found for {owner}/{repo}")

    if not isinstance(release, dict):
        raise RuntimeError(f"Unexpected latest release payload for {owner}/{repo}")

    tag_name = release.get("tag_name")
    html_url = release.get("html_url")
    if not tag_name or not html_url:
        raise RuntimeError(f"Latest release payload missing fields for {owner}/{repo}")
    return LatestRelease(tag_name=tag_name, html_url=html_url)


def issue_title(dependency: DependencyRelease, latest_version: str) -> str:
    return f"chore: bump {dependency.arg_name} from {dependency.current_version} to {latest_version}"


def issue_body(dependency: DependencyRelease, latest_release: LatestRelease, latest_version: str) -> str:
    return "\n".join(
        [
            f"The Dockerfile is pinned to `{dependency.arg_name}={dependency.current_version}`, but `{dependency.upstream_full_name}` has a newer release available.",
            "",
            f"Current version: `{dependency.current_version}`",
            f"Latest version: `{latest_version}`",
            f"Upstream release: {latest_release.html_url}",
            f"Dockerfile source: {dependency.releases_url}",
            "",
            "Update the Dockerfile version arg if the new upstream release is compatible.",
            "",
            "---",
            f"dependency: {dependency.upstream_full_name}",
            f"arg: {dependency.arg_name}",
            f"from: {dependency.current_version}",
            f"to: {latest_version}",
        ]
    )


def search_issue(repository: str, title: str, token: str | None) -> bool:
    query = f'repo:{repository} is:issue "{title}"'
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://api.github.com/search/issues?q={encoded_query}&per_page=1"
    search_result = github_json_request(search_url, token=token)
    if not isinstance(search_result, dict):
        raise RuntimeError("Unexpected search result payload")
    return int(search_result.get("total_count", 0)) > 0


def create_issue(repository: str, title: str, body: str, token: str) -> str:
    owner, repo = repository.split("/", maxsplit=1)
    issue_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    payload = {"title": title, "body": body}
    issue = github_json_request(issue_url, token=token, method="POST", payload=payload)
    if not isinstance(issue, dict) or "html_url" not in issue:
        raise RuntimeError(f"Unexpected issue creation payload for {repository}")
    return str(issue["html_url"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Dockerfile GitHub release pins and open deduplicated issues for outdated versions.")
    parser.add_argument("--dockerfile", type=Path, default=Path("docker/Dockerfile"), help="Path to the Dockerfile to inspect.")
    parser.add_argument("--issue-repo", default=os.getenv("GITHUB_REPOSITORY", ""), help="Repository where issues should be searched/created, for example owner/name.")
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN", ""), help="GitHub token used for API calls.")
    parser.add_argument("--dry-run", action="store_true", help="Report pending issues without creating them.")
    args = parser.parse_args()

    if not args.dockerfile.exists():
        print(f"Dockerfile not found: {args.dockerfile}", file=sys.stderr)
        return 1

    dependencies = parse_dockerfile(args.dockerfile)
    if not dependencies:
        print("No GitHub release dependencies found in Dockerfile.")
        return 0

    if not args.issue_repo:
        print("--issue-repo or GITHUB_REPOSITORY is required.", file=sys.stderr)
        return 1

    token = args.token or None
    if token is None:
        print("Warning: running without GITHUB_TOKEN; GitHub API rate limits may apply.", file=sys.stderr)

    created_count = 0
    skipped_count = 0
    up_to_date_count = 0

    for dependency in dependencies:
        latest_release = get_latest_release(dependency.upstream_owner, dependency.upstream_repo, token)
        latest_version = normalize_version(latest_release.tag_name)
        current_version = normalize_version(dependency.current_version)

        if current_version == latest_version:
            up_to_date_count += 1
            print(f"UP_TO_DATE {dependency.arg_name}={dependency.current_version} ({dependency.upstream_full_name})")
            continue

        title = issue_title(dependency, latest_version)
        if search_issue(args.issue_repo, title, token):
            skipped_count += 1
            print(f"SKIP_DUPLICATE {title}")
            continue

        if args.dry_run:
            created_count += 1
            print(f"DRY_RUN_CREATE {title}")
            continue

        if token is None:
            print("A GitHub token is required to create issues.", file=sys.stderr)
            return 1

        url = create_issue(
            repository=args.issue_repo,
            title=title,
            body=issue_body(dependency, latest_release, latest_version),
            token=token,
        )
        created_count += 1
        print(f"CREATED {title} -> {url}")

    print(
        f"SUMMARY scanned={len(dependencies)} up_to_date={up_to_date_count} skipped_duplicates={skipped_count} created={created_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
