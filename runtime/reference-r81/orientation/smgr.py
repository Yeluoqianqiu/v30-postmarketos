# SPDX-License-Identifier: GPL-2.0-only
"""Read only the Qualcomm Sensor Manager accelerometer over QRTR."""
import ctypes as c
import os
import select
import socket
import struct
import time

AF_QIPCRTR = 42
CTRL = 0xfffffffe
SMGR = 0x100
BUFFER = 0x21
REPORT = 0x22
QMI_HEADER = struct.Struct('<BHHH')
SAMPLE = struct.Struct('<iiiBBH')
lib = c.CDLL(None, use_errno=True)
lib.sendto.restype = lib.recvfrom.restype = c.c_ssize_t


class Address(c.Structure):
    _fields_ = [('family', c.c_ushort), ('node', c.c_uint32), ('port', c.c_uint32)]


class Qrtr:
    def __init__(self):
        self.sock = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
        addr, length = Address(), c.c_uint(c.sizeof(Address))
        if lib.getsockname(self.sock.fileno(), c.byref(addr), c.byref(length)) < 0:
            error = c.get_errno()
            self.sock.close()
            raise OSError(error, os.strerror(error))
        self.node = addr.node

    def send(self, peer, data):
        addr = Address(AF_QIPCRTR, *peer)
        result = lib.sendto(self.sock.fileno(), c.c_char_p(data), c.c_size_t(len(data)),
                            0, c.byref(addr), c.sizeof(addr))
        if result < 0:
            error = c.get_errno()
            raise OSError(error, os.strerror(error))

    def recv(self, timeout):
        if not select.select([self.sock], [], [], max(0, timeout))[0]:
            raise TimeoutError('QRTR receive timed out')
        buf, addr, length = c.create_string_buffer(65536), Address(), c.c_uint(c.sizeof(Address))
        size = lib.recvfrom(self.sock.fileno(), buf, c.c_size_t(len(buf)), 0,
                            c.byref(addr), c.byref(length))
        if size < 0:
            error = c.get_errno()
            raise OSError(error, os.strerror(error))
        return buf.raw[:size], (addr.node, addr.port)

    def discover(self, service, timeout=25):
        self.send((self.node, CTRL), struct.pack('<5I', 10, service, 0, 0, 0))
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            data, (_, source_port) = self.recv(end - time.monotonic())
            if source_port != CTRL or len(data) != 20:
                continue
            command, ident, instance, node, port = struct.unpack('<5I', data)
            if command == 4 and ident == service and node and port:
                return node, port
        raise TimeoutError('Sensor Manager did not publish its QRTR service')


def qmi(kind, txn, message, fields):
    payload = b''.join(struct.pack('<BH', tag, len(value)) + value for tag, value in fields.items())
    return QMI_HEADER.pack(kind, txn, message, len(payload)) + payload


def decode(packet):
    if len(packet) < QMI_HEADER.size:
        raise ValueError('Short QMI packet')
    kind, txn, message, size = QMI_HEADER.unpack_from(packet)
    offset, fields = QMI_HEADER.size, {}
    if len(packet) != offset + size:
        raise ValueError('Bad QMI packet length')
    while offset < len(packet):
        if offset + 3 > len(packet):
            raise ValueError('Short TLV header')
        tag, length = struct.unpack_from('<BH', packet, offset)
        offset += 3
        if offset + length > len(packet) or tag in fields:
            raise ValueError('Bad TLV')
        fields[tag] = packet[offset:offset + length]
        offset += length
    return kind, txn, message, fields


def devices(fields):
    data = fields.get(3, b'')
    if not data:
        raise ValueError('Empty sensor inventory')
    offset, sensors = 1, {}
    for _ in range(data[0]):
        if offset + 2 > len(data):
            raise ValueError('Short sensor inventory')
        ident, length = data[offset:offset + 2]
        offset += 2
        if offset + length > len(data):
            raise ValueError('Short sensor type')
        sensors[ident] = data[offset:offset + length].rstrip(b'\0').decode('ascii')
        offset += length
    if offset != len(data):
        raise ValueError('Extra sensor inventory data')
    return sensors


def request_fields(sensor, rate):
    return {1: bytes([sensor]), 2: b'\x01' if rate else b'\x02',
            3: struct.pack('<I', rate * 65536),
            4: struct.pack('<BBBHHH', 1, sensor, 0, 3, rate, 1) if rate else b'\x00'}


def samples(fields, sensor):
    if fields.get(1) != bytes([sensor]):
        return
    data = fields.get(3, b'')
    if not data or len(data) != 1 + data[0] * SAMPLE.size:
        raise ValueError('Bad accelerometer sample list')
    for x, y, z, flags, quality, offset in SAMPLE.iter_unpack(data[1:]):
        yield (x / 65536, y / 65536, z / 65536)


class Accelerometer:
    def __enter__(self):
        self.qrtr = Qrtr()
        self.txn = 0
        self.enabled = False
        return self

    def discover(self):
        self.peer = self.qrtr.discover(SMGR)
        inventory = devices(self.request(5, {}))
        matches = [ident for ident, name in inventory.items() if name.upper() == 'ACCEL']
        if len(matches) != 1:
            raise RuntimeError(f'Expected one accelerometer. Inventory: {inventory}')
        self.sensor = matches[0]
        return self.peer, inventory

    def request(self, message, fields):
        self.txn += 1
        self.qrtr.send(self.peer, qmi(0, self.txn, message, fields))
        end = time.monotonic() + 5
        while time.monotonic() < end:
            packet, sender = self.qrtr.recv(end - time.monotonic())
            if sender != self.peer:
                continue
            kind, txn, ident, response = decode(packet)
            if (kind, txn, ident) == (2, self.txn, message):
                result = response.get(2, b'')
                if len(result) < 2 or result[:2] != b'\0\0':
                    raise RuntimeError(f'SMGR message {message:#x} result {result.hex()}')
                return response
        raise TimeoutError(f'No response for SMGR message {message:#x}')

    def start(self, rate=15):
        response = self.request(BUFFER, request_fields(self.sensor, rate))
        if response.get(0x11, b'\0') not in (b'\0', b'\1'):
            raise RuntimeError('SMGR refused the accelerometer report: ' + response[0x11].hex())
        self.enabled = True

    def read(self, timeout=2):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            packet, sender = self.qrtr.recv(end - time.monotonic())
            if sender != self.peer:
                continue
            kind, _, ident, fields = decode(packet)
            if (kind, ident) == (4, REPORT):
                return list(samples(fields, self.sensor))
        raise TimeoutError('No accelerometer indication')

    def __exit__(self, *error):
        try:
            if self.enabled:
                self.request(BUFFER, request_fields(self.sensor, 0))
        finally:
            self.qrtr.sock.close()
