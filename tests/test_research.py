import configparser
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from build import ASSET, FILES, ROOT, build


SHELL = os.environ.get("TEST_SH") or shutil.which("sh")
PRODUCT = "CN7NPE.KOR.0000.V039.001.260902"


def posix(path):
    value = str(path.resolve()).replace("\\", "/")
    if len(value) > 2 and value[1] == ":":
        return "/" + value[0].lower() + value[2:]
    return value


class ArchiveTests(unittest.TestCase):
    def test_archive_is_reproducible_and_contains_only_public_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, digest = build(Path(tmp) / "a")
            b, other = build(Path(tmp) / "b")
            self.assertEqual(digest, other)
            self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(), digest)
            with zipfile.ZipFile(a) as archive:
                self.assertEqual(set(archive.namelist()), set(FILES))
                self.assertIsNone(archive.testzip())
                for name in archive.namelist():
                    self.assertNotIn(b"\r", archive.read(name))
                    self.assertFalse(archive.read(name).startswith(b"\xef\xbb\xbf"))
                descriptor = configparser.ConfigParser()
                descriptor.read_string(archive.read("NEMESIS.data").decode())
                self.assertEqual(descriptor["nemesis"]["type"], "execute")
                self.assertIn(descriptor["nemesis"]["path"], archive.namelist())
                self.assertNotIn("NEMESIS.emergency", archive.namelist())
                self.assertIn(b"NOT an exhaust flap controller", archive.read("CN7NPE-EXHAUST-RESEARCH.txt"))
            self.assertIn(ASSET, (a.parent / "SHA256SUMS.txt").read_text())


@unittest.skipUnless(SHELL, "POSIX sh required; set TEST_SH")
class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.usb = self.base / "usb0"
        self.system = self.base / "system"
        self.bin = self.base / "bin"
        self.usb.mkdir()
        self.bin.mkdir()
        (self.system / "framework").mkdir(parents=True)
        (self.system / "app").mkdir()
        (self.usb / "CN7NPE-EXHAUST-RESEARCH.txt").write_text("research")
        (self.system / "framework/automotive.jar").write_bytes(b"FAKE-JAR")
        (self.system / "framework/automotive.odex").write_bytes(b"FAKE-ODEX")
        (self.system / "app/NMode.apk").write_bytes(b"FAKE-APK")
        (self.system / "app/NMode.odex").write_bytes(b"FAKE-ODEX")
        self.product = PRODUCT
        self.platform = "tcc803x"
        self.pm_fails = False
        self.path_override = None
        shell_base = subprocess.run([SHELL, "-c", "pwd -P"], cwd=self.base,
                                    capture_output=True, text=True, check=True, timeout=10).stdout.strip()
        original = (ROOT / "usb/collect.sh").read_text(encoding="utf-8")
        # The shipped script has no test environment switches. Rewrite fixed
        # paths in a disposable copy; never run it against a real /system.
        transformed = original.replace(
            "export PATH=/sbin:/vendor/bin:/system/sbin:/system/bin:/system/xbin",
            'export PATH="$TEST_BIN:' + posix(Path(SHELL).parent) + ':$PATH"',
        ).replace(
            "/storage/usb[0-9]|/mnt/media_rw/usb[0-9]", shell_base + "/usb0"
        ).replace("/system/framework/", posix(self.system) + "/framework/").replace(
            "package:/system/*.apk", "package:" + posix(self.system) + "/*.apk"
        )
        self.script = self.usb / "collect.sh"
        self.script.write_text(transformed, encoding="utf-8", newline="\n")

    def stub(self, name, content):
        target = self.bin / name
        target.write_text("#!/bin/sh\n" + content, encoding="utf-8", newline="\n")
        target.chmod(0o755)

    def run_collector(self):
        self.stub("getprop", '''case "$1" in
ro.build.product) echo "$TEST_PRODUCT" ;;
ro.board.platform) echo "$TEST_PLATFORM" ;;
ro.build.version.release) echo 4.4.2 ;;
ro.build.version.sdk) echo 19 ;;
*) exit 99 ;;
esac
''')
        self.stub("pm", '''[ "$TEST_PM_FAIL" = 1 ] && exit 1
case "$1" in
list) echo package:com.hkmc.app.nmode.ui; echo package:com.hkmc.app.phone; echo package:com.example.nmode ;;
path) echo "package:$TEST_APP" ;;
*) exit 99 ;;
esac
''')
        # Never flush host volumes during tests.
        self.stub("sync", "exit 0\n")
        env = dict(os.environ)
        env.update({
            "TEST_BIN": posix(self.bin), "TEST_PRODUCT": self.product,
            "TEST_PLATFORM": self.platform, "TEST_PM_FAIL": str(int(self.pm_fails)),
            "TEST_APP": self.path_override or posix(self.system / "app/NMode.apk"),
        })
        return subprocess.run([SHELL, self.script.as_posix()], cwd=self.usb, env=env,
                              capture_output=True, text=True, timeout=30)

    def test_complete_copy_and_only_expected_stock_files(self):
        before = {p: p.read_bytes() for p in self.system.rglob("*") if p.is_file()}
        run = self.run_collector()
        self.assertEqual(run.returncode, 0, run.stderr[-1800:] + run.stdout)
        report_dir = self.usb / "CN7NPE-exhaust-private-1"
        report = (report_dir / "report.txt").read_text()
        self.assertIn("collection=COMPLETE", report)
        self.assertIn("flap_control=NOT_IMPLEMENTED", report)
        self.assertEqual(set(p.name for p in (report_dir / "stock").iterdir()),
                         {"automotive.jar", "automotive.odex", "nmode-0.apk", "nmode-0.odex"})
        self.assertEqual((report_dir / "nmode-packages.txt").read_text().strip(), "com.hkmc.app.nmode.ui")
        self.assertFalse(list(report_dir.glob("*.tmp")))
        self.assertEqual(before, {p: p.read_bytes() for p in self.system.rglob("*") if p.is_file()})

    def test_alternative_product_string_is_accepted(self):
        self.product = "CN7NPE.KOR.S5W_M.V039.001.260902"
        self.assertEqual(self.run_collector().returncode, 0)

    def test_wrong_firmware_stops_before_output(self):
        self.product = "CN7NPE.USA.0000.V016.010.260903"
        self.assertEqual(self.run_collector().returncode, 2)
        self.assertFalse(list(self.usb.glob("CN7NPE-exhaust-private-*")))

    def test_wrong_platform_stops_before_output(self):
        self.platform = "other"
        self.assertEqual(self.run_collector().returncode, 2)
        self.assertFalse(list(self.usb.glob("CN7NPE-exhaust-private-*")))

    def test_old_export_is_preserved(self):
        old = self.usb / "CN7NPE-exhaust-private-1"
        old.mkdir()
        (old / "keep").write_text("unchanged")
        self.assertEqual(self.run_collector().returncode, 0)
        self.assertEqual((old / "keep").read_text(), "unchanged")
        self.assertTrue((self.usb / "CN7NPE-exhaust-private-2/report.txt").is_file())

    def test_twenty_existing_exports_are_not_overwritten(self):
        for index in range(1, 21):
            (self.usb / f"CN7NPE-exhaust-private-{index}").mkdir()
        self.assertEqual(self.run_collector().returncode, 3)
        self.assertFalse(list(self.usb.rglob("report.txt")))

    def test_missing_nmode_keeps_incomplete_export(self):
        (self.system / "app/NMode.apk").unlink()
        self.assertEqual(self.run_collector().returncode, 4)
        report = (self.usb / "CN7NPE-exhaust-private-1/report.txt").read_text()
        self.assertIn("collection=INCOMPLETE", report)
        self.assertIn("nmode_apks=0", report)

    def test_missing_automotive_is_incomplete(self):
        for p in (self.system / "framework").iterdir():
            p.unlink()
        self.assertEqual(self.run_collector().returncode, 4)

    def test_package_manager_failure_is_incomplete(self):
        self.pm_fails = True
        self.assertEqual(self.run_collector().returncode, 4)
        report = (self.usb / "CN7NPE-exhaust-private-1/report.txt").read_text()
        self.assertIn("package_list_failed=yes", report)

    def test_non_system_app_path_is_not_copied(self):
        private = self.base / "private.apk"
        private.write_bytes(b"PRIVATE-DATA")
        self.path_override = posix(private)
        self.assertEqual(self.run_collector().returncode, 4)
        for file in (self.usb / "CN7NPE-exhaust-private-1").rglob("*"):
            if file.is_file():
                self.assertNotIn(b"PRIVATE-DATA", file.read_bytes())

    def test_copy_failure_is_reported(self):
        self.stub("cp", "exit 1\n")
        self.assertEqual(self.run_collector().returncode, 4)
        report = (self.usb / "CN7NPE-exhaust-private-1/report.txt").read_text()
        self.assertIn("copy_failed=", report)
        self.assertIn("collection=INCOMPLETE", report)

    def test_production_script_rejects_internal_directory(self):
        original = self.base / "collect.sh"
        original.write_text((ROOT / "usb/collect.sh").read_text(encoding="utf-8"), encoding="utf-8")
        run = subprocess.run([SHELL, original.as_posix()], capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 1)
        self.assertIn("not internal storage", run.stdout)


if __name__ == "__main__":
    unittest.main()
