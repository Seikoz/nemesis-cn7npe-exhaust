import configparser
import hashlib
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
import zipfile

from build import ROOT, TRANSPORT_ASSET, build
import test_research as research

SHELL = research.SHELL
posix = research.posix


class TransportArchiveTests(unittest.TestCase):
    def test_transport_archive_isolated_and_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, digest = build(Path(tmp) / "a", transport=True)
            _, other = build(Path(tmp) / "b", transport=True)
            self.assertEqual(a.name, TRANSPORT_ASSET)
            self.assertEqual(digest, other)
            with zipfile.ZipFile(a) as archive:
                self.assertEqual(set(archive.namelist()), {
                    "NEMESIS.data", "collect-transport.sh", "progress.sh",
                    "CN7NPE-EXHAUST-RESEARCH.txt", "INSTALL-KO.md", "LICENSE",
                })
                self.assertIsNone(archive.testzip())
                config = configparser.ConfigParser()
                config.read_string(archive.read("NEMESIS.data").decode())
                self.assertEqual(config["nemesis"]["path"], "collect-transport.sh")
                self.assertEqual(config["nemesis"]["type"], "execute")
                for name in archive.namelist():
                    self.assertNotIn(b"\r", archive.read(name))
                    self.assertFalse(archive.read(name).startswith(b"\xef\xbb\xbf"))

    def test_conflicting_profiles_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                build(tmp, services=True, transport=True)


@unittest.skipUnless(SHELL, "POSIX sh required; set TEST_SH")
class TransportCollectorTests(unittest.TestCase):
    # Reuse the mock commands and fixed-path isolation, not the old test cases.
    stub = research.CollectorTests.stub

    def setUp(self):
        research.CollectorTests.setUp(self)
        self.vendor = self.base / "vendor"
        for directory in (self.system / "bin", self.system / "lib", self.system / "xbin",
                          self.system / "priv-app", self.vendor / "bin", self.vendor / "lib"):
            directory.mkdir(parents=True, exist_ok=True)
        (self.system / "framework/com.hkmc.ext.hcan.odex").write_bytes(b"HCAN-CODE")
        (self.system / "app/HKMC_EngineerMode.odex").write_bytes(b"ENGINEER-CODE")
        (self.system / "bin/micomd").write_text(
            '#!/bin/sh\necho BAD_EXECUTION >> "$TEST_TRACE"\n', newline="\n")
        (self.system / "bin/micomd").chmod(0o755)
        (self.system / "lib/libhcan.so").write_bytes(b"NATIVE-CODE")
        self.unix = self.base / "unix.txt"
        self.unix.write_text("Num RefCount Path\n1 2 @micom_mux\n2 3 @private_phone\n")
        source = (ROOT / "usb/collect-transport.sh").read_text(encoding="utf-8")
        shell_base = subprocess.run([SHELL, "-c", "pwd -P"], cwd=self.base,
                                    capture_output=True, text=True, check=True, timeout=10).stdout.strip()
        source = source.replace(
            "export PATH=/sbin:/vendor/bin:/system/sbin:/system/bin:/system/xbin",
            'export PATH="$TEST_BIN:' + posix(Path(SHELL).parent) + ':$PATH"',
        ).replace("/storage/usb[0-9]|/mnt/media_rw/usb[0-9]", shell_base + "/usb0")
        source = source.replace("/system/", posix(self.system) + "/")
        source = source.replace("/vendor/", posix(self.vendor) + "/")
        source = source.replace("/proc/net/unix", posix(self.unix))
        self.script.write_text(source, encoding="utf-8", newline="\n")
        # Emulate KitKat toolbox ls (no link-count column). The host wc is
        # used only to create fixture metadata, never by the shipped tool.
        self.real_wc = posix(Path(SHELL).parent / "wc.exe") if os.name == "nt" else shutil.which("wc")
        self.real_ls = posix(Path(SHELL).parent / "ls.exe") if os.name == "nt" else shutil.which("ls")
        self.stub("ls", f'''[ "$1" = -ln ] || exit 92
read bytes unused <<EOF
$("{self.real_wc}" -c "$2")
EOF
echo "-rw-r--r-- 0 0 $bytes 2026-11-19 00:00 $2"
''')
        self.stub("wc", "exit 93\n")
        self.stub("tr", "exit 94\n")
        self.stub("service", '''echo "service:$*" >> "$TEST_TRACE"
[ "$*" = list ] || exit 91
echo '1 com.hkmc.micom.micomdata: [com.hkmc.micom.IMicomDataService]'
echo '2 unrelated_phone: [private]'
''')
        self.stub("ps", '''echo ps >> "$TEST_TRACE"
echo 'root 123 /system/bin/micomd'
echo 'root 124 unrelated_phone'
''')

    def run_collector(self):
        return research.CollectorTests.run_collector(self)

    def output(self):
        return self.usb / "CN7NPE-exhaust-private-1"

    def snapshot(self):
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for root in (self.system, self.vendor) for p in root.rglob("*") if p.is_file()}

    def test_selected_files_only_and_no_binary_execution_or_source_writes(self):
        before = self.snapshot()
        run = self.run_collector()
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        out = self.output()
        self.assertIn("collection=COMPLETE", (out / "result.txt").read_text())
        report = (out / "report.txt").read_text()
        self.assertIn("hcan_odex=1", report)
        self.assertIn("engineering_odex=1", report)
        self.assertIn("native_files=2", report)
        self.assertEqual(len(list((out / "stock").iterdir())), 4)
        self.assertFalse(list(out.glob("*.tmp")))
        self.assertEqual(before, self.snapshot())
        trace = (self.base / "trace.txt").read_text(encoding="utf-8")
        self.assertIn("service:list", trace)
        self.assertNotIn("BAD_EXECUTION", trace)
        self.assertIn("v0.3.0", trace)
        for name in ("services.txt", "processes.txt", "unix-sockets.txt"):
            self.assertNotIn("phone", (out / name).read_text())

    def test_missing_required_hcan_does_not_complete(self):
        (self.system / "framework/com.hkmc.ext.hcan.odex").unlink()
        self.assertEqual(self.run_collector().returncode, 4)
        self.assertNotIn("· 100%", (self.base / "trace.txt").read_text(encoding="utf-8"))

    def test_large_optional_file_skipped_without_false_copy(self):
        big = self.system / "lib/libmicom_big.so"
        with big.open("wb") as stream:
            stream.truncate(8388609)
        self.assertEqual(self.run_collector().returncode, 0)
        report = (self.output() / "report.txt").read_text()
        self.assertIn("skipped_size_limit=", report)
        self.assertFalse(any(p.name.endswith("libmicom_big.so")
                             for p in (self.output() / "stock").iterdir()))

    def test_aggregate_limit_skips_files_and_reports_actual_bytes(self):
        for n in range(3):
            with (self.system / "lib" / f"libmicom_large{n}.so").open("wb") as stream:
                stream.truncate(8388608)
        self.assertEqual(self.run_collector().returncode, 0)
        out = self.output()
        actual = sum(p.stat().st_size for p in (out / "stock").iterdir())
        self.assertLessEqual(actual, 25165824)
        report = (out / "report.txt").read_text()
        self.assertIn(f"stock_copied_bytes={actual}", report)
        self.assertIn("skipped_size_limit=", report)

    @unittest.skipIf(os.name == "nt", "Windows symlink privilege is not assumed; covered on Linux CI")
    def test_symlink_source_is_not_followed(self):
        secret = self.base / "private.txt"
        secret.write_text("UNRELATED_SECRET")
        (self.system / "lib/libmicom_link.so").symlink_to(secret)
        self.assertEqual(self.run_collector().returncode, 0)
        self.assertIn("skipped_symlink=", (self.output() / "report.txt").read_text())
        for p in (self.output() / "stock").iterdir():
            self.assertNotIn(b"UNRELATED_SECRET", p.read_bytes())

    def test_optional_inventory_failure_is_reported(self):
        self.stub("service", "exit 1\n")
        self.assertEqual(self.run_collector().returncode, 0)
        self.assertIn("optional_inventory_failed=service_list", (self.output() / "report.txt").read_text())

    def test_copy_failure_does_not_complete(self):
        self.stub("cp", "exit 1\n")
        self.assertEqual(self.run_collector().returncode, 4)
        self.assertNotIn("· 100%", (self.base / "trace.txt").read_text(encoding="utf-8"))

    def test_wrong_firmware_refused_before_export(self):
        self.product = "OTHER"
        self.assertEqual(self.run_collector().returncode, 2)
        self.assertFalse(list(self.usb.glob("CN7NPE-exhaust-private-*")))

    def test_gnu_ls_size_format_is_accepted_off_car(self):
        self.stub("ls", f'exec "{self.real_ls}" "$@"\n')
        self.assertEqual(self.run_collector().returncode, 0)

    def test_invalid_size_format_stops_before_copy(self):
        self.stub("ls", "echo 'unknown format'\n")
        self.assertEqual(self.run_collector().returncode, 4)
        self.assertFalse(list((self.output() / "stock").iterdir()))
        self.assertNotIn("· 100%", (self.base / "trace.txt").read_text(encoding="utf-8"))

    def test_sync_failure_does_not_complete(self):
        self.sync_fails = True
        self.assertEqual(self.run_collector().returncode, 4)
        self.assertIn("FAILED_SYNC", (self.output() / "result.txt").read_text())
        self.assertNotIn("· 100%", (self.base / "trace.txt").read_text(encoding="utf-8"))

    def test_existing_result_is_preserved(self):
        old = self.output()
        old.mkdir()
        (old / "keep").write_text("unchanged")
        self.assertEqual(self.run_collector().returncode, 0)
        self.assertEqual((old / "keep").read_text(), "unchanged")
        self.assertTrue((self.usb / "CN7NPE-exhaust-private-2/result.txt").exists())
