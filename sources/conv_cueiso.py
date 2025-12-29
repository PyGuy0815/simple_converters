#!/usr/bin/env python3
"""
conv_cueiso.py

Convert between CUE/BIN and ISO images (data CDs only).

Features:
- Multiple input files via -i (supports wildcards)
- Optional output (-o). If omitted, output name is derived from input basename
- Directory processing (-d) and recursive directory processing (-dr)
- Force overwrite (-f) or ask before overwrite (-a)
- Strict but minimal CUE parsing (MODE1 only)

"""
EXAMPLES = """
Examples:
  conv_cueiso.py -i cd.iso
  conv_cueiso.py -i cd_001.cue -i cd_002.cue
  conv_cueiso.py -i cd_game.cue -o game.iso
  conv_cueiso.py -i "*.cue"
  conv_cueiso.py -dr dumps/ -a
"""

import os
import sys
import argparse
import glob
from pathlib import Path

SECTOR_2352 = 2352
SECTOR_2048 = 2048
DATA_OFFSET_2352 = 16  # MODE1 data starts at byte 16


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
        return
    if force:
        return
    if ask:
        if ask_overwrite(path):
            return
        error("Operation aborted by user")
    error(f"{path} already exists (use -f or -a)")


# ------------------------------------------------------------
# CUE parsing (minimal but strict)
# ------------------------------------------------------------
def parse_cue(cue_path: Path):
    bin_file = None
    mode = None

    with cue_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip().upper()

            if line.startswith("FILE"):
                bin_file = line.split('"')[1]

            elif line.startswith("TRACK"):
                if "AUDIO" in line:
                    error(f"{cue_path}: audio tracks are not supported")

                if "MODE1/2352" in line:
                    mode = SECTOR_2352
                elif "MODE1/2048" in line:
                    mode = SECTOR_2048
                else:
                    error(f"{cue_path}: unsupported track mode")

    if not bin_file or not mode:
        error(f"{cue_path}: invalid or unsupported CUE file")

    return bin_file, mode


# ------------------------------------------------------------
# Converters
# ------------------------------------------------------------
def bin_to_iso(bin_path: Path, iso_path: Path, sector_size: int, force: bool, ask: bool):
    check_overwrite(iso_path, force, ask)

    with bin_path.open("rb") as binf, iso_path.open("wb") as isof:
        while True:
            sector = binf.read(sector_size)
            if not sector:
                break

            if sector_size == SECTOR_2352:
                isof.write(sector[DATA_OFFSET_2352:DATA_OFFSET_2352 + SECTOR_2048])
            else:
                isof.write(sector)

    print(f"[OK] BIN → ISO: {iso_path}")


def iso_to_bin(iso_path: Path, bin_path: Path, force: bool, ask: bool):
    cue_path = bin_path.with_suffix(".cue")

    check_overwrite(bin_path, force, ask)
    check_overwrite(cue_path, force, ask)

    with iso_path.open("rb") as isof, bin_path.open("wb") as binf:
        while True:
            data = isof.read(SECTOR_2048)
            if not data:
                break

            sector = bytearray(SECTOR_2352)
            sector[DATA_OFFSET_2352:DATA_OFFSET_2352 + SECTOR_2048] = data
            binf.write(sector)

    cue_path.write_text(
        f'''FILE "{bin_path.name}" BINARY
  TRACK 01 MODE1/2352
    INDEX 01 00:00:00
'''
    )

    print(f"[OK] ISO → BIN+CUE: {bin_path}, {cue_path}")

# ------------------------------------------------------------
# Dispatcher
# ------------------------------------------------------------
def process_file(inp: Path, output: Path | None, force: bool, ask: bool):
    ext = inp.suffix.lower()

    if ext == ".cue":
        bin_name, sector_size = parse_cue(inp)
        bin_path = inp.parent / bin_name
        iso_path = output if output else inp.with_suffix(".iso")
        bin_to_iso(bin_path, iso_path, sector_size, force, ask)

    elif ext == ".iso":
        bin_path = output if output else inp.with_suffix(".bin")
        iso_to_bin(inp, bin_path, force, ask)

    elif ext == ".bin":
        # BIN is accepted silently but converted to ISO
        iso_path = output if output else inp.with_suffix(".iso")
        bin_to_iso(inp, iso_path, SECTOR_2352, force, ask)

    else:
        warn(f"Skipping unsupported file: {inp}")


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Convert CUE ↔ ISO",
        epilog=( EXAMPLES ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("-i", "--input", action="append",
                        help="Input file(s): ISO or CUE (wildcards allowed)")

    parser.add_argument("-o", "--output",
                        help="Output file (single input only)")

    parser.add_argument("-d", "--dir", choices=("iso", "cue"),
                        help="Process directory, filter by file type")

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

    inputs: list[Path] = []

    if args.dir:
        if not args.path:
            error("-d requires a directory path")
        if args.recursive:
            it = Path(args.path).rglob(f"*.{args.dir}")
        else:
            it = Path(args.path).glob(f"*.{args.dir}")
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
