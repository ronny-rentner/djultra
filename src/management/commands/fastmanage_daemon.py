import array
import atexit
import json
import logging
import os
import signal
import shlex
import socket
import sys
import time
from pathlib import Path

import django.core.management as mgmt
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

ENV_PREFIX        = "DJU_DEV_FASTMANAGE"
ENV_DAEMON_SOCKET = f"{ENV_PREFIX}_DAEMON_SOCKET"
ENV_WORKER        = f"{ENV_PREFIX}_WORKER"

CONF_ENABLE        = f"{ENV_PREFIX}_ENABLE"

class FastmanageDaemon:
    def __init__(self, sock_path=None, base_dir=None):
        if sock_path is None and settings._wrapped.is_overridden(ENV_DAEMON_SOCKET):
            sock_path = getattr(settings, ENV_DAEMON_SOCKET)
            if sock_path is None:
                raise ImproperlyConfigured(f"{ENV_DAEMON_SOCKET} must be omitted or set to a filesystem path.")
        self.base_dir = Path(base_dir or os.getcwd())
        self.sock_path = Path(sock_path) if sock_path is not None else self.base_dir / "fastmanage.sock"
        self.server_socket = None
        self.worker_started = {}
        self.original_mgmt = mgmt.ManagementUtility

    def parse_request(self, conn):
        try:
            msg, anc, *_ = conn.recvmsg(65536, socket.CMSG_LEN(3 * array.array("i").itemsize))
        except OSError as exc:
            logger.error(f"recvmsg failed: {exc}")
            return None
        if b"\n" not in msg:
            logger.error("request missing newline separator")
            return None
        env_raw, _, cmd_raw = msg.partition(b"\n")
        try:
            env = json.loads(env_raw.decode() or "{}")
        except Exception as exc:
            logger.error(f"env JSON invalid: {exc}")
            return None
        if env.get(ENV_WORKER) == "1":
            return None
        cmd_line = cmd_raw.decode().strip()
        if not cmd_line:
            logger.error("empty command line")
            return None
        argv = shlex.split(cmd_line)
        fds = []
        for lvl, typ, data in anc:
            if (lvl, typ) == (socket.SOL_SOCKET, socket.SCM_RIGHTS):
                fds.extend(array.array("i", data))
        if len(fds) < 3:
            logger.error("received fewer than 3 fds")
            return None
        return env, argv, fds

    def start(self):
        if self.sock_path.exists():
            try:
                with socket.socket(socket.AF_UNIX) as s:
                    s.connect(str(self.sock_path))
                return
            except OSError:
                self.sock_path.unlink()
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(str(self.sock_path))
        self.server_socket.listen(100)
        os.chmod(str(self.sock_path), 0o660)
        atexit.register(self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGCHLD, self.handle_client_exit)
        while True:
            try:
                conn, _ = self.server_socket.accept()
                logger.debug("daemon accepted connection: ", sys.argv)
            except OSError:
                break
            parsed = self.parse_request(conn)
            if not parsed:
                conn.close()
                continue
            env, argv, fds = parsed
            pid = os.fork()
            if pid == 0:
                signal.signal(signal.SIGCHLD, signal.SIG_DFL)
                self.server_socket.close()
                mgmt.ManagementUtility = self.original_mgmt
                self.run_worker(conn, env, argv, fds)
                os._exit(0)
            else:
                conn.close()
                for fd in fds:
                    os.close(fd)
                self.worker_started[pid] = time.monotonic()
                logger.info(f"spawned worker {pid} {argv}")

    def run_worker(self, conn, env, argv, fds):
        env[ENV_WORKER] = "1"
        os.environ.update(env)
        if (cwd := env.get("PWD")):
            try:
                os.chdir(cwd)
            except OSError:
                pass

        for i in range(0, 3):
            os.dup2(fds[i], i)

        for fd in fds:
            os.close(fd)

        sys.argv = argv
        status = 0
        try:
            mgmt.ManagementUtility().execute(use_socket=False)
        except SystemExit as exc:
            if exc.code is None:
                status = 0
            elif isinstance(exc.code, int):
                status = exc.code
            else:
                print(exc.code, file=sys.stderr)
                status = 1
        # The worker child exits through os._exit(), so Python will not flush these streams for us.
        sys.stdout.flush()
        sys.stderr.flush()
        conn.sendall(f"{status}\n".encode())
        conn.close()

    def shutdown(self, *_):
        if self.server_socket:
            self.server_socket.close()
        if self.sock_path.exists():
            self.sock_path.unlink()
        os._exit(0)

    def handle_client_exit(self, *_):
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
                if pid not in self.worker_started:
                    continue
                dur = time.monotonic() - self.worker_started.pop(pid)
                if os.WIFEXITED(status):
                    logger.info(f"worker {pid} {dur:.3f}s exit {os.WEXITSTATUS(status)}")
                elif os.WIFSIGNALED(status):
                    logger.info(f"worker {pid} sig {os.WTERMSIG(status)} {dur:.3f}s")
            except ChildProcessError:
                break
            except Exception as exc:
                logger.exception(f"reap err {exc}")
                break
