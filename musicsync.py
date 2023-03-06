"""Syncronize a playlist from Music to a disk."""

import logging
import os
import subprocess as sp
import unicodedata
from typing import TypeVar

import click as c
from tqdm import tqdm

logging.basicConfig(level=logging.WARNING, format="%(message)s")
log = logging.getLogger(__name__)

T = TypeVar("T")


def wrap_tqdm(iter: T, *args, **kwargs) -> T:
    if log.level < logging.INFO:
        return iter
    return tqdm(iter, *args, **kwargs)


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def get_playlist_files(playlist: str) -> list[str]:
    """Collect all files from a playlist."""
    script = f"""
        tell application "Music"
            set thePlaylist to the playlist named "{playlist}"
            set output to ""
            repeat with theTrack in (get the location of every track in thePlaylist)
                set output to output & (posix path of theTrack) & "\n"
            end repeat
        end tell
    """
    log.info(f'Collecting songs from playlist "{playlist}"')
    job = sp.run(["osascript", "-e", script], stdout=sp.PIPE)
    files = sorted(f for f in job.stdout.decode("utf-8").splitlines() if f)
    log.info(f"  Collected {len(files)} song{'s' * (len(files) != 1)}")
    return files


def find_root_directory(files: list[str]) -> str:
    prefix = str(max(files, key=len))
    while len(prefix) > 0:
        if all(file.startswith(prefix) for file in files):
            break
        prefix = prefix[:-1]
    log.info(f'Playlist root directory is "{prefix}"')
    return prefix


class directory:
    def __init__(self) -> None:
        self.dirs: dict[str, directory] = {}
        self.files: list[str] = []

    def __str__(self) -> str:
        return f"directory({self.count_dirs()} dirs, {self.count_files()} files)"

    def __repr__(self) -> str:
        return str(self)

    def count_dirs(self) -> int:
        if not hasattr(self, "_num_dirs"):
            n = len(self.dirs) + sum(d.count_dirs() for d in self.dirs.values())
            self._num_dirs = n
        return self._num_dirs

    def count_files(self) -> int:
        if not hasattr(self, "_num_files"):
            n = len(self.files) + sum(d.count_files() for d in self.dirs.values())
            self._num_files = n
        return self._num_files


def build_playlist_tree(songs: list[str], root: str) -> directory:
    log.info("Building playlist song tree")

    tree = directory()
    for entry in songs:
        dirs, file = os.path.split(os.path.relpath(entry, root))

        ptr = tree
        for d in dirs.split(os.path.sep):
            d_norm = norm(d)  # Normed to find keys reliably
            if d_norm not in ptr.dirs:
                ptr.dirs[d_norm] = directory()
            ptr = ptr.dirs[d_norm]
        ptr.files += [file]

    log.info(f"  Found {tree.count_dirs()} dirs and {tree.count_files()} files")
    return tree


def cleanup_volume(volume: str, tree: directory) -> None:
    for pwd, _, files in wrap_tqdm(os.walk(volume), desc="  Processing", leave=False):
        relpath = os.path.relpath(pwd, volume)

        # Delete high-level directories if they don't appear
        truncated = False
        ptr = tree

        if relpath != ".":
            dir_parts = relpath.split(os.path.sep)
            for d in dir_parts:
                d_norm = norm(d)
                if d_norm not in map(norm, ptr.dirs):
                    log.debug(f'  Removing directory "{pwd}"')
                    sp.run(["rm", "-r", f"{pwd}"])
                    truncated = True
                    break
                ptr = ptr.dirs[d_norm]

        if truncated:
            continue

        # Delete files in these directories if the directory exists but they don't
        for file in [f for f in files if norm(f) not in map(norm, ptr.files)]:
            path = os.path.join(pwd, file)
            log.debug(f'  Removing file "{path}"')
            sp.run(["rm", path])


def copy_structure(tree: directory, ptr: str, root: str):
    COPY = ["ditto", "--nocache", "--noextattr", "--noqtn", "--norsrc"]

    for subdir in tree.dirs:
        new_ptr = norm(os.path.join(ptr, subdir))
        new_root = norm(os.path.join(root, subdir))
        if not os.path.isdir(new_ptr):
            log.debug(f'  Creating directory "{new_ptr}"')
            sp.run(["mkdir", "-p", new_ptr])
        copy_structure(tree.dirs[subdir], new_ptr, new_root)

    ptr_n = norm(ptr)
    for file in wrap_tqdm(tree.files, desc="  " + ptr, leave=False):
        src = os.path.join(root, file)
        dst = norm(os.path.join(ptr_n, file))  # Copy to a normalized path

        src_st = os.stat(src)
        if not os.path.exists(dst) or src_st.st_size != os.stat(dst).st_size:
            log.debug(f'  dittoing file "{src}"')
            sp.run(COPY + [src, ptr_n])


@c.command()
@c.help_option("-h", "--help")
@c.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable debug logging.",
)
@c.option(
    "--playlist",
    "-p",
    metavar="NAME",
    type=str,
    default="Selected for Car",
    help="Apple Music playlist to sync.",
)
@c.argument(
    "VOLUME",
    type=c.Path(exists=True, file_okay=False, writable=True),
)
def main(playlist: str, volume: str, verbose: bool) -> None:
    log.setLevel(logging.DEBUG if verbose else logging.INFO)

    songlist = get_playlist_files(playlist)
    root = find_root_directory(songlist)
    songtree = build_playlist_tree(songlist, root)

    log.info(f'Removing extra files from "{volume}"')
    cleanup_volume(volume, songtree)

    log.info(f'Copying new files from "{playlist}" to "{volume}" ')
    copy_structure(songtree, volume, root)


if __name__ == "__main__":
    main()
