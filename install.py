#!/usr/bin/env python3
"""Install selected repository skills using only the Python standard library."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4

NAME = 'fpga-rtl-standards'
REPOSITORY = 'https://github.com/black-pigeon/fpga_skills_for_codex'
ROOT = Path(__file__).resolve().parent


def install(destination, update=False, name=NAME):
    source = ROOT / 'skills' / name
    if not (source / 'SKILL.md').is_file():
        raise ValueError('Missing skill source: ' + str(source))
    target = destination / name
    if target.is_symlink():
        raise ValueError('Destination is a symlink; update its source instead: ' + str(target))
    if target.exists() and not target.is_dir():
        raise ValueError('Destination is not a directory: ' + str(target))
    if target.exists() and not update:
        raise ValueError('Already installed. Use --update to replace it with a backup: ' + str(target))
    for entry in source.rglob('*'):
        if entry.is_symlink():
            raise ValueError('Skill source must not contain symlinks: ' + str(entry))
    try:
        commit = subprocess.check_output(
            ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None  # ZIP downloads need not contain .git metadata.
    destination.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.TemporaryDirectory(prefix='.fpga-skill-stage-', dir=destination.parent) as tmp:
        stage = Path(tmp) / name
        shutil.copytree(source, stage, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        receipt = {
            'repository': REPOSITORY, 'path': 'skills/' + name,
            'commit': commit, 'installed_at': datetime.now(timezone.utc).isoformat(),
        }
        (stage / '.install-source.json').write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
        )
        if target.exists():
            backup_root = destination.parent / 'skill-backups'
            backup_root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            backup = backup_root / (name + '-' + stamp + '-' + uuid4().hex[:8])
            target.rename(backup)
        try:
            stage.rename(target)
        except OSError:
            if backup is not None:
                backup.rename(target)
            raise
    print('Installed: ' + str(target))
    if backup is not None:
        print('Previous version backed up: ' + str(backup))
    print('The skill can be discovered on the next Codex turn. If absent, restart Codex.')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, default=Path.home() / '.agents' / 'skills',
                        help='Skills directory (default: ~/.agents/skills)')
    choices=sorted(p.name for p in (ROOT/'skills').iterdir() if (p/'SKILL.md').is_file())
    parser.add_argument('--skill', nargs='+', choices=choices, default=[NAME],
                        help='Skills to install (default: fpga-rtl-standards)')
    parser.add_argument('--update', action='store_true',
                        help='Replace an installed copy, preserving a backup outside the skills directory')
    args = parser.parse_args()
    try:
        for name in dict.fromkeys(args.skill):
            install(args.dest.expanduser().absolute(), args.update, name)
    except (OSError, ValueError) as exc:
        print('Install failed: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
