#!/usr/bin/env python3
"""Host side of the core protocol (boards/core/firmware/PROTOCOL.md).

Python 3 standard library only: plain sockets, no drivers, no privileges.

  thlcore.py 192.168.1.50 STATUS
  thlcore.py 192.168.1.50 SSR 3 SET v=24 i=5 hot=0 noreg=0
  thlcore.py 192.168.1.50 --stream          # STREAM ON, print decoded samples
  thlcore.py 192.168.1.50 --serial 1        # raw bytes of serial port 1 to stdout

As a library:

  with Core("192.168.1.50") as c:
      print(c.cmd("ID"))                    # -> Response(ok, code, text, lines)
"""
import argparse
import select
import socket
import struct
import sys
from dataclasses import dataclass, field

CMD_PORT = 5000
SER_PORT = 5000                 # + port number 1-4
STREAM_PORT = 5100              # + SSR node 0-15


@dataclass
class Response:
    ok: bool
    code: int                   # 0 for OK, else the ERR code
    text: str                   # rest of the final line
    lines: list = field(default_factory=list)   # "* " data lines, prefix removed

    def __str__(self):
        body = "".join(f"* {l}\n" for l in self.lines)
        return body + (f"OK {self.text}".rstrip() if self.ok else f"ERR {self.code} {self.text}")


class Core:
    def __init__(self, host, port=CMD_PORT, timeout=3.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.buf = b""

    def close(self):
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _line(self):
        while b"\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("core closed the connection")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return line.decode("ascii", "replace").rstrip("\r")

    def cmd(self, command):
        """Send one command and read its complete response."""
        self.sock.sendall(command.encode("ascii") + b"\n")
        lines = []
        while True:
            line = self._line()
            if line.startswith("* "):
                lines.append(line[2:])
            elif line == "OK" or line.startswith("OK "):
                return Response(True, 0, line[3:], lines)
            elif line.startswith("ERR "):
                parts = line.split(" ", 2)
                return Response(False, int(parts[1]), parts[2] if len(parts) > 2 else "", lines)
            else:
                lines.append(line)      # tolerate unprefixed text


def decode_stream(data):
    """Binary SSR datagram -> (node, seq, state, faults, [(ms, vin, vout, iavg, ipeak), ...]) in V/A."""
    magic, ver, node, n, seq, state, _, faults = struct.unpack_from("<BBBBIBBH", data)
    if magic != 0x53 or ver != 1:
        raise ValueError("not an SSR stream datagram")
    samples = []
    for k in range(n):
        t, vin, vout, iavg, ipeak = struct.unpack_from("<IHHHH", data, 12 + 12 * k)
        samples.append((t, vin / 100, vout / 100, iavg / 100, ipeak / 100))
    return node, seq, state, faults, samples


def run_stream(host, batch):
    socks = []
    for node in range(16):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("", STREAM_PORT + node))
        socks.append(s)
    with Core(host) as c:
        print(c.cmd(f"STREAM ON batch={batch}"), file=sys.stderr)
        last_seq = {}
        try:
            while True:
                ready, _, _ = select.select(socks, [], [], 1.0)
                for s in ready:
                    node, seq, state, faults, samples = decode_stream(s.recv(2048))
                    if node in last_seq and seq != last_seq[node] + 1:
                        print(f"# node {node}: {seq - last_seq[node] - 1} datagram(s) lost", file=sys.stderr)
                    last_seq[node] = seq
                    for t, vin, vout, iavg, ipeak in samples:
                        print(f"{node} {t} {vin:.2f} {vout:.2f} {iavg:.2f} {ipeak:.2f} state={state} faults=0x{faults:04X}")
                c.cmd("ID")             # keeps the host watchdog fed if WDOG is set
        except KeyboardInterrupt:
            print(c.cmd("STREAM OFF"), file=sys.stderr)


def run_serial(host, port):
    s = socket.create_connection((host, SER_PORT + port))
    try:
        while True:
            data = s.recv(4096)
            if not data:
                break
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    except KeyboardInterrupt:
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host")
    ap.add_argument("command", nargs="*", help="one command, e.g. STATUS")
    ap.add_argument("--stream", action="store_true", help="STREAM ON and print SSR samples")
    ap.add_argument("--batch", type=int, default=5)
    ap.add_argument("--serial", type=int, metavar="N", help="dump serial port N (1-4)")
    a = ap.parse_args()
    if a.stream:
        run_stream(a.host, a.batch)
    elif a.serial:
        run_serial(a.host, a.serial)
    elif a.command:
        with Core(a.host) as c:
            r = c.cmd(" ".join(a.command))
            print(r)
            sys.exit(0 if r.ok else 1)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
