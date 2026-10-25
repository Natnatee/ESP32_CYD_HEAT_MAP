"""PlatformIO post-link guard and standalone Xtensa compiler stack-frame regression.
Run: python tools/check_stack_frames.py [--build-dir .pio/build/cyd_ili9341]
Requires a build with -fstack-usage; checks compiler output, not host ABI estimates.
This per-function bound is not proof of total runtime stack depth; measure Serial h too.
"""
from pathlib import Path
import argparse
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
UI_LIMIT = 1024


def inspect_frames(build_dir):
    frames = []
    required = {"main.cpp"}
    found = set()
    for path in Path(build_dir).rglob("*.su"):
        source = next((name for name in required if path.name.startswith(name + ".") or path.name == name[:-4] + ".su"), None)
        if source is None:
            continue
        found.add(source)
        for row in path.read_text(encoding="utf-8").splitlines():
            parts = row.rsplit("\t", 2)
            if len(parts) != 3:
                raise AssertionError(f"Unrecognized stack report: {path}: {row}")
            location, size, kind = parts
            function = re.sub(r"^.*?:\d+:\d+:", "", location)
            frames.append((source, function, int(size), kind))
    assert found == required, f"Missing .su reports for {required - found}; run pio run -e cyd_ili9341 with -fstack-usage"
    failures = []
    watched = {"loop": False}
    for source, function, size, kind in frames:
        limit = UI_LIMIT
        if limit is not None and (size > limit or ("dynamic" in kind and "bounded" not in kind)):
            failures.append(f"{source}: {function}: {size} bytes ({kind}), limit {limit}")
        if "void loop()" in function:
            watched["loop"] = True
    assert all(watched.values()), f"Missing required compiled functions: {watched}"
    assert not failures, "Stack frame regression:\n" + "\n".join(failures)
    return frames


def report(build_dir):
    frames = inspect_frames(build_dir)
    for source, function, size, kind in frames:
        if "void loop()" in function:
            print(f"STACK {function}: {size} bytes ({kind})")
    print(f"PASS: main.cpp frames <= {UI_LIMIT} bytes (max {max(size for _, _, size, _ in frames)}).")


def self_test():
    with tempfile.TemporaryDirectory(prefix="cyd-frame-test-") as folder:
        folder = Path(folder)
        main = folder / "main.cpp.su"
        main.write_text("src/main.cpp:1:1:void loop()\t96\tstatic\n", encoding="utf-8")
        inspect_frames(folder)
        # Actual offending frame size from the SHA-matched crash ELF must be rejected.
        main.write_text("src/main.cpp:1:1:void loop()\t3440\tstatic\n", encoding="utf-8")
        try:
            inspect_frames(folder)
        except AssertionError as error:
            assert "Stack frame regression" in str(error)
        else:
            raise AssertionError("Old 3440-byte loop frame escaped regression guard")
    print("PASS: frame guard rejects original crash-sized loop frame.")


if "Import" in globals():
    Import("env")

    def after_link(source, target, env):
        report(Path(env.subst("$BUILD_DIR")))

    env.AddPostAction("$BUILD_DIR/${PROGNAME}.elf", after_link)
elif __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / ".pio/build/cyd_ili9341")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    report(args.build_dir)
