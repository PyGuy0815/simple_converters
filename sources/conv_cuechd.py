#!/usr/bin/env python3
"""
conv_cuechd.py [-h] [-i INPUT] [-o OUTPUT] [-d {cue,chd,iso,bin}] [-r] [-f | -a] [path]

Convert between CUE/BIN/ISO and CHD images using chdman.

Primary use:
- CUE/BIN → CHD
- CHD → CUE/BIN

Explicit conversions:
- ISO → CHD
- BIN → CHD

Requirements:
- chdman must be installed and available in PATH

Features:
- Multiple input files via -i (supports wildcards)
- Optional output (-o). If omitted, output name is derived from input basename
- Directory processing (-d) optional recursive (-r)
- Force overwrite (-f) or ask before overwrite (-a)
- Strict but minimal CUE parsing (MODE1 only)
"""

EXAMPLES = """
Examples:
  conv_cuechd.py -i game.cue
  conv_cuechd.py -i game.iso
  conv_cuechd.py -i game.chd
  conv_cuechd.py -i "*.cue"
  conv_cuechd.py -d cue discs/ -r -f
  conv_cuechd.py -d chd discs/
"""
import platform
import sys
import argparse
import subprocess
import shutil
import glob
from pathlib import Path

# ------------------------------------------------------------
# Utility
# ------------------------------------------------------------
def error(msg):
    print(f"[ERR] {msg}", file=sys.stderr)
    sys.exit(1)


def warn(msg):
    print(f"[WARN] {msg}", file=sys.stderr)


def ask_overwrite(path: Path) -> bool:
    while True:
        ans = input(f'Overwrite "{path}"? [y/N]: ').strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no", ""):
            return False


def check_overwrite(path: Path, force: bool, ask: bool):
    if not path.exists():
        return True
    if force:
        return True
    if ask:
        return ask_overwrite(path)
    warn(f"{path} already exists (use -f or -a)")
    return False



def ask_install_chdman() -> bool:
    while True:
        ans = input(f'chdman not found. Try to install? [y/N]: ').strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no", ""):
            return False

def check_chdman():
    if shutil.which("chdmang"):
        return True
        
    if not ask_install_chdman():
        return False
        
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            if not shutil.which("brew"):
                error("Homebrew not found. Install Homebrew first: https://brew.sh")
            subprocess.run(["brew", "install", "mame"], check=True)

        elif system == "Linux":
            if shutil.which("apt"):
                subprocess.run(["sudo", "apt", "update"], check=True)
                subprocess.run(["sudo", "apt", "install", "-y", "mame-tools"], check=True)
            elif shutil.which("dnf"):
                subprocess.run(["sudo", "dnf", "install", "-y", "mame-tools"], check=True)
            elif shutil.which("pacman"):
                subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "mame-tools"], check=True)
            else:
                error("Unsupported Linux distribution (no apt/dnf/pacman)")

        elif system == "Windows":
            error(
                "Automatic installation on Windows is not supported.\n"
                "Please download MAME from:\n"
                "  https://www.mamedev.org/release.html\n"
                "Extract chdman.exe and add it to your PATH."
            )

        else:
            error(f"Unsupported operating system: {system}")

    except subprocess.CalledProcessError:
        error("Failed to install chdman")

    if not shutil.which("chdman"):
        print("chdman installation attempted but still not found in PATH")
        return False

    print("[OK] chdman installed successfully")
    return True
        


def run(cmd: list[str]):
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        error("chdman failed")


# ------------------------------------------------------------
# Converters
# ------------------------------------------------------------
def to_chd(inp: Path, out: Path, force: bool, ask: bool):
    if not check_overwrite(out, force, ask):
        return

    cmd = [
        "chdman",
        "createcd",
        "-i", str(inp),
        "-o", str(out)
    ]

    run(cmd)
    print(f"[OK] → CHD: {out}")


def chd_to_cue(inp: Path, out: Path, force: bool, ask: bool):
    if not check_overwrite(out, force, ask):
        return

    cmd = [
        "chdman",
        "extractcd",
        "-i", str(inp),
        "-o", str(out)
    ]

    run(cmd)
    print(f"[OK] CHD → CUE/BIN: {out}")


# ------------------------------------------------------------
# Dispatcher
# ------------------------------------------------------------
def process_file(inp: Path, output: Path | None, force: bool, ask: bool):
    ext = inp.suffix.lower()

    if ext in (".cue", ".iso", ".bin"):
        out = output if output else inp.with_suffix(".chd")
        to_chd(inp, out, force, ask)

    elif ext == ".chd":
        out = output if output else inp.with_suffix(".cue")
        chd_to_cue(inp, out, force, ask)

    else:
        warn(f"Skipping unsupported file: {inp}")


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Convert CUE/BIN/ISO ↔ CHD using chdman",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("-i", "--input", action="append",
                        help="Input file(s): CUE, CHD, ISO or BIN (wildcards allowed)")

    parser.add_argument("-o", "--output",
                        help="Output file (single input only)")

    parser.add_argument("-d", "--dir",
                        choices=("cue", "chd", "iso", "bin"),
                        help="Process directory by extension")

    parser.add_argument("path", nargs="?",
                        help="Directory path (required with -d)")

    parser.add_argument("-r", "--recursive",
                        action="store_true",
                        help="Recursive directory processing (requires -d)")

    overwrite = parser.add_mutually_exclusive_group()
    overwrite.add_argument("-f", "--force", action="store_true",
                           help="Overwrite existing files without asking")
    overwrite.add_argument("-a", "--ask", action="store_true",
                           help="Ask before overwriting existing files")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if not check_chdman():
        error("chdman not found in PATH (please install MAME/chdman) ")

    inputs: list[Path] = []

    if args.dir:
        if not args.path:
            error("-d requires a directory path")
        base = Path(args.path)
        pattern = f"*.{args.dir}"
        it = base.rglob(pattern) if args.recursive else base.glob(pattern)
        inputs.extend(p for p in it if p.is_file())

    elif args.recursive:
        error("-r can only be used together with -d")

    if args.input:
        for pattern in args.input:
            matches = glob.glob(pattern)
            if not matches:
                warn(f"No match for pattern: {pattern}")
            inputs.extend(Path(m) for m in matches)

    if not inputs:
        error("No input files specified")

    if args.output and len(inputs) > 1:
        error("-o can only be used with a single input file")

    output = Path(args.output) if args.output else None

    for inp in inputs:
        process_file(inp, output, args.force, args.ask)


if __name__ == "__main__":
    main()
