"""Read one narrowly specified Java serialization form without deserializing objects.

No Java runtime, imports from the input, object instantiation, network, or vehicle I/O.
Only the known DiagProtocolType with one 32-byte array is accepted.
"""
import argparse
import json
from pathlib import Path
import struct

CLASS_NAME = "com.hkmc.telematics.hscan.CanManager.Diag.data.DiagProtocolType"
FIELD_NAME = "DIAG_PORTOCAL_TYPE_LIST"
SERIAL_UID = -7672126317923522678
BYTE_ARRAY_UID = bytes.fromhex("acf317f8060854e0")
LIMIT = 4096
PROTOCOLS = {0: "UNKNOWN", 1: "KWP", 2: "UDS"}


class InvalidState(ValueError):
    pass


class Reader:
    def __init__(self, data):
        if not 0 < len(data) <= LIMIT:
            raise InvalidState("State must contain 1..4096 bytes")
        self.data = data
        self.offset = 0

    def take(self, count):
        if count < 0 or self.offset + count > len(self.data):
            raise InvalidState("Truncated state")
        result = self.data[self.offset:self.offset + count]
        self.offset += count
        return result

    def expect(self, expected):
        if self.take(len(expected)) != expected:
            raise InvalidState("Unexpected serialization structure")

    def utf(self, expected):
        length = struct.unpack(">H", self.take(2))[0]
        if self.take(length) != expected.encode("ascii"):
            raise InvalidState("Unexpected class, field, or type name")


def decode(data):
    r = Reader(data)
    r.expect(bytes.fromhex("aced00057372"))  # Header, object, class descriptor.
    r.utf(CLASS_NAME)
    r.expect(struct.pack(">q", SERIAL_UID))
    r.expect(bytes.fromhex("0200015b"))  # Serializable, one field, array type.
    r.utf(FIELD_NAME)
    r.expect(b"\x74")  # Type name is a string, not executable class data.
    r.utf("[B")
    r.expect(bytes.fromhex("78707572"))  # End annotations, null super, array, class.
    r.utf("[B")
    r.expect(BYTE_ARRAY_UID)
    r.expect(bytes.fromhex("0200007870"))
    if struct.unpack(">I", r.take(4))[0] != 32:
        raise InvalidState("Protocol array must contain exactly 32 entries")
    values = list(r.take(32))
    if r.offset != len(data):
        raise InvalidState("Trailing data or additional object is not accepted")
    if any(value not in PROTOCOLS for value in values):
        raise InvalidState("Unsupported protocol value; do not guess its meaning")
    return {
        "schema": "cn7npe-saved-protocol-state-v1",
        "source_kind": "saved_cache_not_live_ECU_response",
        "ems_index": 4,
        "ems_saved_protocol": PROTOCOLS[values[4]],
        "ems_mapping": "stock_default_EMS_slot_not_verified_active_route",
        "cs_ems_index": 30,
        "cs_ems_saved_protocol": PROTOCOLS[values[30]],
        "protocol_values": values,
        "ECU_exchange": "NOT_TESTED",
        "AEV_control": "UNVERIFIED",
        "note": "Saved UNKNOWN/KWP/UDS selection does not establish current routing, AEV support, or release behavior. Provisioned EMS routing may use another logical slot.",
    }


def read_state(path):
    path = Path(path)
    if path.is_symlink():
        raise InvalidState("Symlink input is not accepted")
    with path.open("rb") as stream:
        return decode(stream.read(LIMIT + 1))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    args = parser.parse_args(argv)
    try:
        result = read_state(args.state)
    except (OSError, InvalidState) as error:
        parser.exit(2, f"Cannot decode state: {error}\n")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
