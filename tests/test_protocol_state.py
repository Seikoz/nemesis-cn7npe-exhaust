import configparser
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zipfile

from build import PROTOCOL_STATE_ASSET, ROOT, build
from tools.decode_protocol_state import InvalidState, decode, read_state
import test_research as research
import test_transport as transport

SHELL = research.SHELL
posix = research.posix


def fixture(ems=2, cs_ems=0):
    """Synthetic stream assembled from the Java serialization wire grammar.

    Contains no vehicle data and does not use the decoder to generate its input.
    """
    def utf(value):
        data = value.encode("ascii")
        return struct.pack(">H", len(data)) + data
    values = bytearray(32)
    values[4] = ems
    values[30] = cs_ems
    return (bytes.fromhex("aced00057372")
            + utf("com.hkmc.telematics.hscan.CanManager.Diag.data.DiagProtocolType")
            + struct.pack(">q", -7672126317923522678)
            + bytes.fromhex("0200015b") + utf("DIAG_PORTOCAL_TYPE_LIST")
            + b"\x74" + utf("[B") + bytes.fromhex("78707572")
            + utf("[B") + bytes.fromhex("acf317f8060854e00200007870")
            + struct.pack(">I", 32) + values)


class ProtocolDecoderTests(unittest.TestCase):
    def test_saved_uds_is_not_reported_as_live_control(self):
        result = decode(fixture())
        self.assertEqual(result["ems_saved_protocol"], "UDS")
        self.assertEqual(result["cs_ems_saved_protocol"], "UNKNOWN")
        self.assertEqual(result["AEV_control"], "UNVERIFIED")
        self.assertEqual(result["ECU_exchange"], "NOT_TESTED")
        self.assertIn("not_verified_active_route", result["ems_mapping"])

    def test_unknown_and_kwp_are_distinguished(self):
        self.assertEqual(decode(fixture(0))["ems_saved_protocol"], "UNKNOWN")
        self.assertEqual(decode(fixture(1, 2))["ems_saved_protocol"], "KWP")
        self.assertEqual(decode(fixture(1, 2))["cs_ems_saved_protocol"], "UDS")

    def test_other_serialized_class_or_field_is_rejected(self):
        for old, new in ((b"DiagProtocolType", b"OtherObjectType!"),
                         (b"DIAG_PORTOCAL_TYPE_LIST", b"DIAG_PORTOCAL_TYPE_LAST")):
            with self.subTest(old=old), self.assertRaises(InvalidState):
                decode(fixture().replace(old, new))

    def test_other_serial_version_or_array_class_is_rejected(self):
        data = fixture()
        for old, new in ((struct.pack(">q", -7672126317923522678), b"\x00" * 8),
                         (bytes.fromhex("acf317f8060854e0"), b"\x00" * 8)):
            with self.subTest(old=old.hex()), self.assertRaises(InvalidState):
                decode(data.replace(old, new))

    def test_truncation_at_every_byte_is_rejected(self):
        data = fixture()
        for size in range(len(data)):
            with self.subTest(size=size), self.assertRaises(InvalidState):
                decode(data[:size])

    def test_oversize_trailing_data_or_appended_object_is_rejected(self):
        for data in (b"X" * 4097, fixture() + b"\x73", fixture() + fixture()):
            with self.subTest(size=len(data)), self.assertRaises(InvalidState):
                decode(data)

    def test_unknown_flag_is_not_guessed(self):
        with self.assertRaises(InvalidState):
            decode(fixture(3))

    def test_unbounded_array_length_is_rejected(self):
        data = fixture()
        for length in (0, 31, 33, 0xffffffff):
            with self.subTest(length=length), self.assertRaises(InvalidState):
                decode(data[:-36] + struct.pack(">I", length) + data[-32:])

    def test_read_from_file_is_bounded_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.dat"
            path.write_bytes(fixture())
            before = path.read_bytes()
            self.assertEqual(read_state(path)["ems_saved_protocol"], "UDS")
            self.assertEqual(path.read_bytes(), before)
            path.write_bytes(b"X" * 4097)
            with self.assertRaises(InvalidState):
                read_state(path)


class ProtocolArchiveTests(unittest.TestCase):
    def test_exact_reproducible_tool_only_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, digest = build(Path(tmp) / "a", protocol_state=True)
            _, other = build(Path(tmp) / "b", protocol_state=True)
            self.assertEqual(path.name, PROTOCOL_STATE_ASSET)
            self.assertEqual(digest, other)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(set(archive.namelist()), {
                    "NEMESIS.data", "collect-protocol-state.sh", "progress.sh",
                    "CN7NPE-EXHAUST-RESEARCH.txt", "INSTALL-KO.md", "LICENSE",
                    "pc/decode_protocol_state.py",
                })
                self.assertIsNone(archive.testzip())
                config = configparser.ConfigParser()
                config.read_string(archive.read("NEMESIS.data").decode())
                self.assertEqual(config["nemesis"]["path"], "collect-protocol-state.sh")
                self.assertIn(b"0.3.2-local", archive.read("CN7NPE-EXHAUST-RESEARCH.txt"))
                for name in archive.namelist():
                    self.assertNotIn(b"\r", archive.read(name))

    def test_all_conflicting_profiles_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for profile in ("services", "transport", "hcan_service"):
                with self.subTest(profile=profile), self.assertRaises(ValueError):
                    build(tmp, protocol_state=True, **{profile: True})


@unittest.skipUnless(SHELL, "POSIX sh required; set TEST_SH")
class ProtocolStateCollectorTests(unittest.TestCase):
    stub = research.CollectorTests.stub
    run_collector = research.CollectorTests.run_collector
    output = transport.TransportCollectorTests.output

    def setUp(self):
        transport.TransportCollectorTests.setUp(self)
        self.data = self.base / "data"
        self.securedata = self.base / "securedata"
        self.state = self.data / "misc/infobank/diagInfo/DiagProtocalType.dat"
        self.other_state = self.securedata / "misc/infobank/diagInfo/DiagProtocalType.dat"
        for path in (self.state, self.other_state):
            path.parent.mkdir(parents=True)
        self.state.write_bytes(fixture())
        (self.data / "personal-secret.dat").write_bytes(b"UNRELATED_PRIVATE_DATA")
        source = (ROOT / "usb/collect-protocol-state.sh").read_text(encoding="utf-8")
        shell_base = subprocess.run([SHELL, "-c", "pwd -P"], cwd=self.base,
                                    capture_output=True, text=True, check=True, timeout=10).stdout.strip()
        source = source.replace(
            "export PATH=/sbin:/vendor/bin:/system/sbin:/system/bin:/system/xbin",
            'export PATH="$TEST_BIN:' + posix(Path(SHELL).parent) + ':$PATH"',
        ).replace("/storage/usb[0-9]|/mnt/media_rw/usb[0-9]", shell_base + "/usb0")
        source = source.replace("/securedata/", posix(self.securedata) + "/")
        source = source.replace("/data/", posix(self.data) + "/")
        self.script.write_text(source, encoding="utf-8", newline="\n")
        for name in ("service", "ps", "dumpsys", "content", "logcat", "micomlog"):
            self.stub(name, 'echo FORBIDDEN_RUNTIME_CALL >> "$TEST_TRACE"; exit 91\n')

    def report(self):
        return (self.output() / "report.txt").read_text()

    def snapshot(self):
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for root in (self.system, self.vendor, self.data, self.securedata)
                for p in root.rglob("*") if p.is_file()}

    def test_only_state_copied_no_source_writes_or_runtime_calls(self):
        before = self.snapshot()
        run = self.run_collector()
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        files = list((self.output() / "state").iterdir())
        self.assertEqual([p.name for p in files], ["data_diagInfo_DiagProtocalType.dat"])
        self.assertEqual(decode(files[0].read_bytes())["ems_saved_protocol"], "UDS")
        self.assertEqual(before, self.snapshot())
        trace = (self.base / "trace.txt").read_text(encoding="utf-8")
        self.assertNotIn("FORBIDDEN_RUNTIME_CALL", trace)
        self.assertNotIn("BAD_EXECUTION", trace)
        self.assertLess(trace.rindex("sync\n"), trace.index("· 100%"))
        self.assertIn("protocol_state=AVAILABLE_FOR_OFFLINE_DECODE", self.report())

    def test_both_missing_does_not_create_cache_or_claim_protocol(self):
        self.state.unlink()
        self.assertEqual(self.run_collector().returncode, 0)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.other_state.exists())
        self.assertIn("protocol_state=UNAVAILABLE", self.report())
        self.assertEqual(list((self.output() / "state").iterdir()), [])

    def test_both_roots_preserved_as_distinct_inputs(self):
        self.other_state.write_bytes(fixture(1))
        self.assertEqual(self.run_collector().returncode, 0)
        files = sorted((self.output() / "state").iterdir())
        self.assertEqual(len(files), 2)
        self.assertEqual({decode(p.read_bytes())["ems_saved_protocol"] for p in files}, {"KWP", "UDS"})

    def test_oversize_state_is_skipped(self):
        self.state.write_bytes(b"X" * 4097)
        self.assertEqual(self.run_collector().returncode, 0)
        self.assertIn("skipped_size_limit=", self.report())
        self.assertIn("protocol_state=UNAVAILABLE", self.report())
        self.assertEqual(list((self.output() / "state").iterdir()), [])

    def test_empty_state_is_skipped(self):
        self.state.write_bytes(b"")
        self.assertEqual(self.run_collector().returncode, 0)
        self.assertIn("skipped_empty=", self.report())

    def test_copy_failure_not_completed(self):
        self.stub("cp", "exit 1\n")
        self.assertEqual(self.run_collector().returncode, 4)
        self.assertNotIn("· 100%", (self.base / "trace.txt").read_text(encoding="utf-8"))

    def test_invalid_size_format_not_completed(self):
        self.stub("ls", "echo invalid\n")
        self.assertEqual(self.run_collector().returncode, 4)

    def test_sync_failure_not_completed(self):
        self.sync_fails = True
        self.assertEqual(self.run_collector().returncode, 4)
        self.assertIn("FAILED_SYNC", (self.output() / "result.txt").read_text())

    def test_wrong_firmware_refused(self):
        self.product = "OTHER"
        self.assertEqual(self.run_collector().returncode, 2)
        self.assertFalse(list(self.usb.glob("CN7NPE-exhaust-private-*")))

    def test_old_result_not_overwritten(self):
        self.output().mkdir()
        (self.output() / "keep").write_text("unchanged")
        self.assertEqual(self.run_collector().returncode, 0)
        self.assertEqual((self.output() / "keep").read_text(), "unchanged")

    @unittest.skipIf(os.name == "nt", "Windows symlink privilege not assumed")
    def test_parent_symlink_is_not_followed(self):
        self.state.unlink()
        self.state.parent.rmdir()
        external = self.base / "external"
        external.mkdir()
        (external / self.state.name).write_bytes(fixture())
        self.state.parent.symlink_to(external, target_is_directory=True)
        self.assertEqual(self.run_collector().returncode, 0)
        self.assertIn("skipped_symlink_path=", self.report())
        self.assertEqual(list((self.output() / "state").iterdir()), [])
