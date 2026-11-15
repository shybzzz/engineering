#!/usr/bin/env python3
"""Check a plugin marketplace repository before committing.

Usage:  python check_marketplace.py <path to the marketplace repo>

Exit code 0 - everything is fine; 1 - problems found (listed one per line);
2 - the path is not a marketplace repo. Standard library only.

What is checked
  - .claude-plugin/marketplace.json and every plugins/*/.claude-plugin/plugin.json:
    not empty, valid JSON, required fields present;
  - every plugin listed in marketplace.json has a folder and a manifest with
    the same name, and every folder under plugins/ is listed;
  - every plugins/*/skills/*/SKILL.md: not empty, frontmatter with a `name`
    equal to the folder name and a non-empty `description`;
  - no file tracked by git has become empty (0 bytes) in the working tree;
  - a plugin whose files differ from HEAD has a version different from HEAD.
"""

import json
import os
import re
import subprocess
import sys

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def read_json(path, problems, label):
    """Return the parsed JSON object, or None after recording the problem."""
    if not os.path.isfile(path):
        problems.append(f"{label}: file is missing")
        return None
    with open(path, "rb") as f:
        raw = f.read()
    if not raw.strip():
        problems.append(f"{label}: file is EMPTY (0 bytes of content)")
        return None
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as e:
        problems.append(f"{label}: not valid JSON ({e})")
        return None
    if not isinstance(data, dict):
        problems.append(f"{label}: top level must be an object")
        return None
    return data


def frontmatter(path):
    """Return the frontmatter fields of a SKILL.md as a dict (top-level scalars only)."""
    with open(path, "rb") as f:
        text = f.read().decode("utf-8-sig", errors="replace")
    if not text.strip():
        return None
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip().strip("'\"")
    return {}  # no closing '---'


def git(repo, *args):
    """Run git in the repo; return stdout as text, or None if git is unavailable or fails."""
    try:
        r = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", *args],
                           capture_output=True, check=False)
    except OSError:
        return None
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def check(repo):
    problems = []
    notes = []

    market = read_json(os.path.join(repo, ".claude-plugin", "marketplace.json"), problems,
                       ".claude-plugin/marketplace.json")
    if market is None:
        return problems, notes
    listed = {}
    for entry in market.get("plugins") or []:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not name:
            problems.append("marketplace.json: a plugin entry without a name")
            continue
        listed[name] = entry
        for field in ("source", "description"):
            if not entry.get(field):
                problems.append(f"marketplace.json: plugin '{name}' has no '{field}'")
    if not market.get("name"):
        problems.append("marketplace.json: no 'name'")
    if not listed:
        problems.append("marketplace.json: no plugins listed")

    plugins_dir = os.path.join(repo, "plugins")
    folders = sorted(d for d in os.listdir(plugins_dir)
                     if os.path.isdir(os.path.join(plugins_dir, d))) if os.path.isdir(plugins_dir) else []
    for name in folders:
        if name not in listed:
            problems.append(f"plugins/{name}: folder is not listed in marketplace.json")

    versions = {}
    for name, entry in listed.items():
        source = str(entry.get("source") or "").replace("\\", "/")
        rel = source[2:] if source.startswith("./") else source
        root = os.path.join(repo, *rel.split("/")) if rel else ""
        if not rel or not os.path.isdir(root):
            problems.append(f"plugin '{name}': source folder '{source}' does not exist")
            continue
        label = f"{rel}/.claude-plugin/plugin.json"
        manifest = read_json(os.path.join(root, ".claude-plugin", "plugin.json"), problems, label)
        if manifest is not None:
            if manifest.get("name") != name:
                problems.append(f"{label}: name is {manifest.get('name')!r}, expected {name!r}")
            if not manifest.get("description"):
                problems.append(f"{label}: no 'description'")
            version = manifest.get("version")
            if not isinstance(version, str) or not VERSION_RE.match(version):
                problems.append(f"{label}: version {version!r} is not of the form X.Y.Z")
            else:
                versions[rel] = version

        skills_dir = os.path.join(root, "skills")
        skills = sorted(os.listdir(skills_dir)) if os.path.isdir(skills_dir) else []
        for skill in skills:
            skill_md = os.path.join(skills_dir, skill, "SKILL.md")
            where = f"{rel}/skills/{skill}/SKILL.md"
            if not os.path.isdir(os.path.join(skills_dir, skill)):
                continue
            if not os.path.isfile(skill_md):
                problems.append(f"{where}: file is missing")
                continue
            fm = frontmatter(skill_md)
            if fm is None:
                problems.append(f"{where}: file is EMPTY")
            elif not fm:
                problems.append(f"{where}: no frontmatter (--- name / description ---)")
            else:
                if fm.get("name") != skill:
                    problems.append(f"{where}: frontmatter name is {fm.get('name')!r}, expected {skill!r}")
                if not fm.get("description"):
                    problems.append(f"{where}: frontmatter has no description")

    # --- comparisons with the last commit (skipped when this is not a git repo) ---
    tree = git(repo, "ls-tree", "-r", "-l", "-z", "HEAD")
    if tree is None:
        notes.append("not a git repository (or no commits yet): comparisons with HEAD skipped")
        return problems, notes

    for record in tree.split("\0"):
        if "\t" not in record:
            continue
        meta, path = record.split("\t", 1)
        size = meta.split()[-1]
        full = os.path.join(repo, *path.split("/"))
        if size.isdigit() and int(size) > 0 and os.path.isfile(full) and os.path.getsize(full) == 0:
            problems.append(f"{path}: file became EMPTY (it has {size} bytes in the last commit)")

    status = git(repo, "status", "--porcelain", "-z", "--untracked-files=all") or ""
    changed = [item[3:] for item in status.split("\0") if len(item) > 3]
    for rel, version in versions.items():
        if not any(path.startswith(rel + "/") for path in changed):
            continue
        old_raw = git(repo, "show", f"HEAD:{rel}/.claude-plugin/plugin.json")
        try:
            old_version = json.loads(old_raw).get("version") if old_raw and old_raw.strip() else None
        except ValueError:
            old_version = None
        if old_version == version:
            problems.append(f"{rel}: files changed but the version is still {version} - bump it")
        else:
            notes.append(f"{rel}: version {old_version} -> {version}")

    return problems, notes


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    repo = os.path.abspath(os.path.expanduser(sys.argv[1]))
    if not os.path.isfile(os.path.join(repo, ".claude-plugin", "marketplace.json")):
        print(f"NOT A MARKETPLACE: {repo} has no .claude-plugin/marketplace.json")
        return 2
    problems, notes = check(repo)
    for note in notes:
        print("note: " + note)
    if problems:
        print(f"FAILED: {len(problems)} problem(s) - do not commit")
        for p in problems:
            print("  - " + p)
        return 1
    print("OK: marketplace is consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
