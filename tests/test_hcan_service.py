import configparser
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from build import HCAN_SERVICE_ASSET, ROOT, build
import test_research as research
import test_transport as transport

SHELL = research.SHELL
posix = research.posix


class HcanServiceArchiveTests(unittest.TestCase):
    def test_reproducible_public_only_archive_and_correct_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, digest = build(Path(tmp) / "a", hcan_service=True)
            _, other = build(Path(tmp) / "b", hcan_service=True)
            self.assertEqual(path.name, HCAN_SERVICE_ASSET)
            self.assertEqual(digest, other)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(set(archive.namelist()), {
                    "NEMESIS.data", "collect-hcan-service.sh", "progress.sh",
                    "CN7NPE-EXHAUST-RESEARCH.txt", "INSTALL-KO.md", "LICENSE",
                })
                self.assertIsNone(archive.testzip())
                config = configparser.ConfigParser()
                config.read_string(archive.read("NEMESIS.data").decode())
                self.assertEqual(config["nemesis"]["path"], "collect-hcan-service.sh")
                self.assertEqual(config["nemesis"]["type"], "execute")
                self.assertIn(b"collector 0.3.1", archive.read("CN7NPE-EXHAUST-RESEARCH.txt"))
                for name in archive.namelist():
                    self.assertNotIn(b"\r", archive.read(name))
                    self.assertFalse(archive.read(name).startswith(b"\xef\xbb\xbf"))

    def test_conflicting_profiles_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for option in ("services", "transport"):
                with self.subTest(option=option), self.assertRaises(ValueError):
                    build(tmp, hcan_service=True, **{option: True})


@unittest.skipUnless(SHELL, "POSIX sh required; set TEST_SH")
class HcanServiceCollectorTests(unittest.TestCase):
    # Reuse fixture isolation and commands without inheriting other test cases.
    stub = research.CollectorTests.stub
    run_collector = research.CollectorTests.run_collector
    output = transport.TransportCollectorTests.output
    snapshot = transport.TransportCollectorTests.snapshot

    def setUp(self):
        transport.TransportCollectorTests.setUp(self)
        self.jar = self.system / "framework/com.infobank.jar"
        self.odex = self.system / "framework/com.infobank.odex"
        self.jni = self.system / "lib/libautoframework_jni.so"
        self.jar.write_bytes(b"INFOBANK-JAR")
        self.odex.write_bytes(b"INFOBANK-ODEX")
        self.jni.write_bytes(b"JNI-LIBRARY")
        source = (ROOT / "usb/collect-hcan-service.sh").read_text(encoding="utf-8")
        shell_base = subprocess.run([SHELL, "-c", "pwd -P"], cwd=self.base,
                                    capture_output=True, text=True, check=True, timeout=10).stdout.strip()
        source = source.replace(
            "export PATH=/sbin:/vendor/bin:/system/sbin:/system/bin:/system/xbin",
            'export PATH="$TEST_BIN:' + posix(Path(SHELL).parent) + ':$PATH"',
        ).replace("/storage/usb[0-9]|/mnt/media_rw/usb[0-9]", shell_base + "/usb0")
        source = source.replace("/system/", posix(self.system) + "/")
        self.script.write_text(source, encoding="utf-8", newline="\n")
        # Runtime inventory and control interfaces are not needed by this profile.
        for name in ("service", "ps", "dumpsys", "logcat", "micomlog"):
            self.stub(name, 'echo FORBIDDEN_RUNTIME_CALL >> "$TEST_TRACE"; exit 91\n')

    def assert_not_complete(self, run):
        self.assertEqual(run.returncode, 4, run.stderr + run.stdout)
        self.assertNotIn("· 100%", (self.base / "trace.txt").read_text(encoding="utf-8"))

    def test_only_three_targets_no_inventory_execution_or_source_changes(self):
        before = self.snapshot()
        run = self.run_collector()
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        out = self.output()
        self.assertEqual(set(p.name for p in (out / "stock").iterdir()), {
            "system_framework_com.infobank.jar", "system_framework_com.infobank.odex",
            "system_lib_libautoframework_jni.so",
        })
        self.assertEqual(before, self.snapshot())
        trace = (self.base / "trace.txt").read_text(encoding="utf-8")
        self.assertNotIn("FORBIDDEN_RUNTIME_CALL", trace)
        self.assertNotIn("BAD_EXECUTION", trace)
        self.assertIn("v0.3.1", trace)
        self.assertLess(trace.rindex("sync\n"), trace.index("· 100%"))
        self.assertIn("collection=COMPLETE", (out / "result.txt").read_text())
        self.assertFalse(list(out.glob("*.tmp")))

    def test_missing_required_odex_is_incomplete(self):
        self.odex.unlink()
        self.assert_not_complete(self.run_collector())
        self.assertIn("INCOMPLETE", (self.output() / "result.txt").read_text())

    def test_empty_required_jar_is_incomplete(self):
        self.jar.write_bytes(b"")
        self.assert_not_complete(self.run_collector())
        self.assertIn("skipped_empty=", (self.output() / "report.txt").read_text())

    def test_optional_jni_missing_is_recorded_and_completes(self):
        self.jni.unlink()
        self.assertEqual(self.run_collector().returncode, 0)
        report = (self.output() / "report.txt").read_text()
        self.assertIn("jni_library=0", report)
        self.assertIn("skipped_files=1", report)

    def test_required_file_above_limit_is_not_copied_or_completed(self):
        with self.odex.open("wb") as stream:
            stream.truncate(8388609)
        self.assert_not_complete(self.run_collector())
        self.assertFalse((self.output() / "stock/system_framework_com.infobank.odex").exists())
        self.assertIn("skipped_size_limit=", (self.output() / "report.txt").read_text())

    def test_total_limit_preserves_required_pair_and_skips_optional(self):
        for path in (self.jar, self.odex):
            with path.open("wb") as stream:
                stream.truncate(8388608)
        self.assertEqual(self.run_collector().returncode, 0)
        out = self.output()
        actual = sum(p.stat().st_size for p in (out / "stock").iterdir())
        self.assertEqual(actual, 16777216)
        self.assertIn("jni_library=0", (out / "report.txt").read_text())

    def test_copy_failure_does_not_complete(self):
        self.stub("cp", "exit 1\n")
        self.assert_not_complete(self.run_collector())

    def test_size_format_failure_does_not_complete(self):
        self.stub("ls", "echo unknown-format\n")
        self.assert_not_complete(self.run_collector())
        self.assertFalse(list((self.output() / "stock").iterdir()))

    def test_gnu_ls_format_also_works(self):
        self.stub("ls", f'exec "{self.real_ls}" "$@"\n')
        self.assertEqual(self.run_collector().returncode, 0)

    def test_sync_failure_does_not_complete(self):
        self.sync_fails = True
        self.assert_not_complete(self.run_collector())
        self.assertIn("FAILED_SYNC", (self.output() / "result.txt").read_text())

    def test_existing_result_preserved(self):
        old = self.output()
        old.mkdir()
        (old / "keep").write_text("unchanged")
        self.assertEqual(self.run_collector().returncode, 0)
        self.assertEqual((old / "keep").read_text(), "unchanged")
        self.assertTrue((self.usb / "CN7NPE-exhaust-private-2/result.txt").exists())

    def test_wrong_firmware_refused_before_output(self):
        self.product = "OTHER"
        self.assertEqual(self.run_collector().returncode, 2)
        self.assertFalse(list(self.usb.glob("CN7NPE-exhaust-private-*")))

    @unittest.skipIf(os.name == "nt", "Windows symlink privilege not assumed; covered on Linux CI")
    def test_required_symlink_is_not_followed(self):
        self.odex.unlink()
        self.odex.symlink_to(self.system / "framework/automotive.odex")
        self.assert_not_complete(self.run_collector())
        self.assertIn("skipped_symlink=", (self.output() / "report.txt").read_text())
