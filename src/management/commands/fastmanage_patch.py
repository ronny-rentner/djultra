#!/usr/bin/env python
"""
fastmanage – a fast, daemon-based version of Django CLI management utility (client only)
"""

import os
import sys
import socket
import array
import time
import json
import shlex
from pathlib import Path

import django.core.management as mgmt

def dbg(msg):
    return
    ts = time.strftime('%Y-%m-%d %H:%M:%S.%f')
    print(f"[fastmanage][{ts}][{os.getpid()}] {msg}", file=sys.stderr)

class SocketManagementUtility(mgmt.ManagementUtility):
    def __init__(self, argv=None):
        super().__init__(argv)
        # Use project or current working dir for socket path
        self.base_dir = Path.cwd()
        self.sock_path = self.base_dir / "fastmanage.sock"

        self.original_execute = mgmt.ManagementUtility.execute

    def execute(self, *args, use_socket=True, **kwargs):
        if not use_socket or os.getenv("DJU_DEV_FASTMANAGE_WORKER") == "1":
            # Just act as the normal Django ManagementUtility
            os.environ["DJU_DEV_FASTMANAGE_WORKER"] = "1"
            return super().execute(*args, **kwargs)

        #return super().execute(*args, **kwargs)

        dbg(f"Client: execute called with argv={self.argv}")

        if not self.sock_path.exists():
            return super().execute(*args, **kwargs)
            #dbg("Client: socket not found. Fastmanage daemon must be running.")
            #raise SystemExit("fastmanage: daemon socket not found – is the daemon running?")

        cli = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            cli.connect(str(self.sock_path))
        except OSError as e:
            dbg(f"Client: connect failed: {e}")
            dbg(f"Client: executing directly")
            return super().execute(*args, **kwargs)
            #raise SystemExit(f"fastmanage: could not connect to daemon: {e}\nMaybe stale socket? {self.sock_path}")

        # Serialize environment and command
        env_json = json.dumps(dict(os.environ)).encode()
        cmd = (shlex.join(self.argv) + "\n").encode()
        payload = env_json + b"\n" + cmd

        #dbg(f"Client payload: {payload}")

        anc = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [0, 1, 2]).tobytes())]
        cli.sendmsg([payload], anc)

        # Wait for socket close (which signals completion)
        while cli.recv(4096):
            pass
        cli.close()

# Patch Django globally
mgmt.ManagementUtility = SocketManagementUtility
dbg("SocketManagementUtility installed. All commands will use the daemon (client only).")
