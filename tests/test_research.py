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

    def test_service_archive_selects_incremental_collector(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = build(tmp, services=True)
            with zipfile.ZipFile(path) as archive:
                self.assertIn(b"path=collect-services.sh", archive.read("NEMESIS.data"))
                self.assertIn("collect-services.sh", archive.namelist())
                self.assertIn(b"--services-only", archive.read("collect-services.sh"))


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
        self.path_fails = False
        self.ui_fails = False
        self.ui_text_error = False
        self.sync_fails = False
        self.services_only = False
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
        # Shorten polling only in this disposable test copy. Production uses
        # real seconds and never reads a test environment override.
        progress = (ROOT / "usb/progress.sh").read_text(encoding="utf-8")
        progress = progress.replace("sleep 1", "sleep 0.01").replace("sleep 2", "sleep 0.01")
        (self.usb / "progress.sh").write_text(progress, encoding="utf-8", newline="\n")

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
path) [ "$TEST_PATH_FAIL" = 1 ] && exit 1; echo "package:$TEST_APP" ;;
*) exit 99 ;;
esac
''')
        # Never flush host volumes during tests.
        self.stub("sync", 'echo sync >> "$TEST_TRACE"; [ "$TEST_SYNC_FAIL" != 1 ]\n')
        self.stub("am", '''[ "$TEST_UI_FAIL" = 1 ] && exit 1
if [ "$TEST_UI_TEXT_ERROR" = 1 ]; then echo 'Error: Activity class does not exist'; exit 0; fi
echo "$*" >> "$TEST_TRACE"
echo Starting: Intent
''')
        env = dict(os.environ)
        env.update({
            "TEST_BIN": posix(self.bin), "TEST_PRODUCT": self.product,
            "TEST_PLATFORM": self.platform, "TEST_PM_FAIL": str(int(self.pm_fails)),
            "TEST_APP": self.path_override or posix(self.system / "app/NMode.apk"),
            "TEST_PATH_FAIL": str(int(self.path_fails)),
            "TEST_UI_FAIL": str(int(self.ui_fails)),
            "TEST_UI_TEXT_ERROR": str(int(self.ui_text_error)),
            "TEST_SYNC_FAIL": str(int(self.sync_fails)),
            "TEST_TRACE": posix(self.base / "trace.txt"),
        })
        args = [SHELL, self.script.as_posix()]
        if self.services_only:
            args.append("--services-only")
        return subprocess.run(args, cwd=self.usb, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=60)

    def test_complete_copy_and_only_expected_stock_files(self):
        before = {p: p.read_bytes() for p in self.system.rglob("*") if p.is_file()}
        run = self.run_collector()
        self.assertEqual(run.returncode, 0, run.stderr[-1800:] + run.stdout)
        report_dir = self.usb / "CN7NPE-exhaust-private-1"
        report = (report_dir / "report.txt").read_text()
        self.assertIn("collection=COMPLETE", (report_dir / "result.txt").read_text())
        self.assertIn("flap_control=NOT_IMPLEMENTED", report)
        self.assertEqual(set(p.name for p in (report_dir / "stock").iterdir()),
                         {"automotive.jar", "automotive.odex", "nmode-0.apk", "nmode-0.odex"})
        self.assertEqual((report_dir / "nmode-packages.txt").read_text().strip(), "com.hkmc.app.nmode.ui")
        self.assertFalse(list(report_dir.glob("*.tmp")))
        self.assertEqual(before, {p: p.read_bytes() for p in self.system.rglob("*") if p.is_file()})
        events = (report_dir / "events.log").read_text(encoding="utf-8").splitlines()
        percentages = [int(line.split()[0].split("=")[1]) for line in events]
        self.assertEqual(percentages, sorted(percentages))
        self.assertEqual(percentages[-1], 100)
        trace = (self.base / "trace.txt").read_text(encoding="utf-8")
        self.assertLess(trace.rindex("sync\n"), trace.index("· 100%"))
        self.assertIn("state=COMPLETE", (report_dir / "progress.txt").read_text(encoding="utf-8"))

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
        report = (self.usb / "CN7NPE-exhaust-private-1/report.txt").read_text(encoding="utf-8")
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
        self.assertIn("collection=FAILED_COPY", report)
        self.assertNotIn("· 100%", (self.base / "trace.txt").read_text(encoding="utf-8"))

    def test_ui_launch_failure_stops_before_copy(self):
        self.ui_fails = True
        self.assertEqual(self.run_collector().returncode, 5)
        self.assertFalse(list(self.usb.rglob("*.jar")))

    def test_activity_manager_text_error_stops_before_copy(self):
        self.ui_text_error = True
        self.assertEqual(self.run_collector().returncode, 5)
        self.assertFalse(list(self.usb.rglob("*.jar")))

    def test_sync_failure_never_displays_100_percent(self):
        self.sync_fails = True
        self.assertEqual(self.run_collector().returncode, 4)
        trace = (self.base / "trace.txt").read_text(encoding="utf-8")
        self.assertNotIn("· 100%", trace)
        self.assertIn("state=FAILED", (self.usb / "CN7NPE-exhaust-private-1/progress.txt").read_text(encoding="utf-8"))
        report = (self.usb / "CN7NPE-exhaust-private-1/report.txt").read_text(encoding="utf-8")
        self.assertNotIn("collection=COMPLETE", report)
        self.assertIn("collection=FAILED_SYNC", (self.usb / "CN7NPE-exhaust-private-1/result.txt").read_text())

    def test_service_only_does_not_query_or_copy_nmode(self):
        self.services_only = True
        self.pm_fails = True
        (self.system / "framework/automotive-service.odex").write_bytes(b"FAKE-SERVICE")
        run = self.run_collector()
        self.assertEqual(run.returncode, 0, run.stderr[-1800:] + run.stdout)
        out = self.usb / "CN7NPE-exhaust-private-1"
        self.assertEqual(set(p.name for p in (out / "stock").iterdir()), {"automotive-service.odex"})
        self.assertIn("profile=services", (out / "report.txt").read_text())
        self.assertIn("collection=COMPLETE", (out / "result.txt").read_text())

    def test_service_only_requires_service_implementation(self):
        self.services_only = True
        (self.system / "framework/automotive-service.jar").write_bytes(b"STUB-JAR")
        self.assertEqual(self.run_collector().returncode, 4)
        self.assertNotIn("· 100%", (self.base / "trace.txt").read_text(encoding="utf-8"))

    def test_package_path_failure_never_displays_100_percent(self):
        self.path_fails = True
        self.assertEqual(self.run_collector().returncode, 4)
        trace = (self.base / "trace.txt").read_text(encoding="utf-8")
        self.assertNotIn("· 100%", trace)

    def test_copy_timeout_keeps_partial_files_and_returns_failure(self):
        self.stub("cp", 'exec sleep 5\n')
        self.assertEqual(self.run_collector().returncode, 4)
        trace = (self.base / "trace.txt").read_text(encoding="utf-8")
        self.assertNotIn("· 100%", trace)
        self.assertIn("collection=FAILED_COPY", (self.usb / "CN7NPE-exhaust-private-1/report.txt").read_text(encoding="utf-8"))

    def test_production_script_rejects_internal_directory(self):
        original = self.base / "collect.sh"
        original.write_text((ROOT / "usb/collect.sh").read_text(encoding="utf-8"), encoding="utf-8")
        run = subprocess.run([SHELL, original.as_posix()], capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 1)
        self.assertIn("not internal storage", run.stdout)


if __name__ == "__main__":
    unittest.main()
