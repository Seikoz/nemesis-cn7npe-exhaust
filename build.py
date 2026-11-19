"""Build a deterministic USB research archive; never package collected files."""
from pathlib import Path
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = "0.2.1"
ASSET = f"NEMESIS-CN7NPE-Exhaust-Research-v{VERSION}-USB.zip"
FILES = {
    "NEMESIS.data": ROOT / "usb/NEMESIS.data",
    "collect.sh": ROOT / "usb/collect.sh",
    "progress.sh": ROOT / "usb/progress.sh",
    "CN7NPE-EXHAUST-RESEARCH.txt": ROOT / "usb/CN7NPE-EXHAUST-RESEARCH.txt",
    "INSTALL-KO.md": ROOT / "usb/INSTALL-KO.md",
    "LICENSE": ROOT / "LICENSE",
}


def build(destination=None, services=False):
    destination = Path(destination) if destination else ROOT / "dist"
    destination.mkdir(parents=True, exist_ok=True)
    asset_name = ASSET.replace("Exhaust-Research", "Exhaust-Service-Research") if services else ASSET
    archive = destination / asset_name
    files = dict(FILES)
    if services:
        files["NEMESIS.data"] = ROOT / "usb/NEMESIS-services.data"
        files["collect-services.sh"] = ROOT / "usb/collect-services.sh"
        files["INSTALL-KO.md"] = ROOT / "usb/INSTALL-SERVICES-KO.md"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for name, source in sorted(files.items()):
            data = source.read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode("utf-8")
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 19, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(info, data)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination / "SHA256SUMS.txt").write_text(f"{digest}  {asset_name}\n", encoding="ascii")
    return archive, digest


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--services", action="store_true")
    args = parser.parse_args()
    archive, digest = build(services=args.services)
    print(archive)
    print(digest)
