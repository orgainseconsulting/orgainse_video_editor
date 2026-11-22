"""Package the committed editor and its pinned source projects for Windows setup."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED, ZIP_STORED

ROOT = Path(__file__).resolve().parent
COMPRESSED = {".png", ".webp", ".jpg", ".jpeg", ".gif", ".mp4", ".mov", ".mp3", ".woff2", ".zip", ".gz"}


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def add_tree(archive, repo, revision, prefix):
    # Read the requested commit directly. Local recordings, tools and untracked files stay private.
    with subprocess.Popen(["git", "-C", str(repo), "archive", "--format=tar", revision],
                          stdout=subprocess.PIPE) as proc:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tree:
            for entry in tree:
                if not (entry.isfile() or entry.issym()):
                    continue
                name = prefix + entry.name
                info = ZipInfo(name)
                info.create_system = 3
                info.external_attr = ((0o120777 if entry.issym() else 0o100000 | entry.mode) << 16)
                info.compress_type = ZIP_STORED if Path(name).suffix.lower() in COMPRESSED else ZIP_DEFLATED
                if entry.issym():
                    archive.writestr(info, entry.linkname.encode())
                else:
                    with tree.extractfile(entry) as src, archive.open(info, "w", force_zip64=True) as dst:
                        shutil.copyfileobj(src, dst, length=1024*1024)
        if proc.wait():
            raise RuntimeError(f"Could not archive {repo.name} at {revision}")


def build(target):
    revision = git(ROOT, "rev-parse", "HEAD").decode().strip()
    entries = git(ROOT, "ls-tree", "-rz", revision).decode("utf-8").split("\0")
    pins = []
    for entry in entries:
        if entry.startswith("160000 commit "):
            header, name = entry.split("\t", 1)
            pins.append((name, header.split()[-1]))
    with tempfile.TemporaryDirectory(dir=target.parent) as temp:
        output = Path(temp) / "release.zip"
        with ZipFile(output, "w", allowZip64=True) as archive:
            add_tree(archive, ROOT, revision, "")
            for name, sha in pins:
                add_tree(archive, ROOT / name, sha, name + "/")
            manifest = [f"{revision}  orgainse_video_editor"] + [f"{sha}  {name}" for name, sha in pins]
            archive.writestr("SOURCE_REVISIONS.txt", "\n".join(manifest) + "\n")
        with ZipFile(output) as archive:
            if broken := archive.testzip():
                raise ValueError(f"Damaged archive entry: {broken}")
        os.replace(output, target)
    print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output.resolve())
