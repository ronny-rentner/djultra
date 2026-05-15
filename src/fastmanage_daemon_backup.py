import array
import atexit
import json
import logging
import os
import signal
import socket
import sys
import time
from pathlib import Path

import django.core.management as mgmt
from django.conf import settings

logger = logging.getLogger(__name__)

class FastmanageDaemon:
    def __init__(self, sock_path=None, base_dir=None):
        sock_path = sock_path or getattr(settings, 'DJU_DEV_FASTMANAGE_DAEMON_SOCKET', None)
        self.base_dir = Path(base_dir or os.getcwd())
        self.sock_path = Path(sock_path or self.base_dir / "fastmanage.sock")
        self.server_socket = None

    def start(self):
        logger.debug(f"Launching daemon: sock_path={self.sock_path}")

        # Clean up any stale socket
        if self.sock_path.exists():
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(str(self.sock_path))
                sock.close()
                logger.warn("Daemon already running, aborting launch")
                return
            except OSError:
                logger.warning("Removing stale socket file")
                self.sock_path.unlink()

        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(str(self.sock_path))
        self.server_socket.listen(100)
        self.server_socket.setblocking(True)
        os.chmod(str(self.sock_path), 0o660)

        atexit.register(self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGCHLD, self.handle_child_exit)

        try:
            logger.debug("Daemon main loop started, awaiting connections")
            while True:
                try:
                    conn, _ = self.server_socket.accept()
                except OSError:
                    logger.info("Daemon: socket closed, exiting")
                    break

                pid = os.fork()
                if pid == 0:
                    # In worker child
                    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
                    self.server_socket.close()
                    self.handle_client(conn)
                    os._exit(0)
                else:
                    conn.close()
                    logger.info(f"Daemon: spawned worker pid={pid}")

        finally:
            self.shutdown()

    def handle_client(self, conn):
        worker_pid = os.getpid()
        logger.info(f"Worker[{worker_pid}]: start handling client")
        t0 = time.time()

        msg, anc, _, _ = conn.recvmsg(
            65536, socket.CMSG_LEN(3 * array.array("i").itemsize)
        )
        t_recv = time.time()
        logger.info(f"Worker[{worker_pid}]: received payload in {t_recv - t0:.6f}s")

        env_raw, sep, cmd_raw = msg.partition(b"\n")
        try:
            client_env = json.loads(env_raw.decode())
            os.environ.update(client_env)
            logger.info(f"Worker[{worker_pid}]: environment updated with {len(client_env)} vars")
        except Exception as e:
            logger.error(f"Worker[{worker_pid}]: failed to decode env ({e})")

        client_cwd = client_env.get('PWD')
        if client_cwd:
            try:
                os.chdir(client_cwd)
                logger.info(f"Worker[{worker_pid}]: cwd changed to {client_cwd}")
            except OSError as e:
                logger.error(f"Worker[{worker_pid}]: failed to chdir to {client_cwd}: {e}")
        else:
            logger.info(f"Worker[{worker_pid}]: no PWD in env, staying in {self.base_dir}")

        fds = []
        for level, typ, data in anc:
            if level == socket.SOL_SOCKET and typ == socket.SCM_RIGHTS:
                fds.extend(array.array("i", data))
        if len(fds) >= 3:
            os.dup2(fds[0], 0)
            os.dup2(fds[1], 1)
            os.dup2(fds[2], 2)

        args = cmd_raw.decode().strip().split()
        sys.argv = args
        logger.info(f"Worker[{worker_pid}]: sys.argv updated to {sys.argv}")

        # Import and execute Django command as usual
        try:
            mgmt.ManagementUtility().execute(use_socket=False)
        except SystemExit:
            pass

        conn.close()
        logger.info(f"Worker[{worker_pid}]: finished handling client")

    def shutdown(self, signum=None, frame=None):
        logger.info("Daemon shutting down")
        if self.server_socket:
            self.server_socket.close()
        if self.sock_path.exists():
            self.sock_path.unlink()
        # Only force exit if called directly from signal handler, not atexit
        #if signum is not None:
        os._exit(0)

    def handle_child_exit(self, signum, frame):
        """
        Signal handler for SIGCHLD: reaps all finished worker children,
        logs their PID and exit status.
        """
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
                if os.WIFEXITED(status):
                    exit_code = os.WEXITSTATUS(status)
                    logger.info(
                        f"Worker [{pid}] finished with exit code {exit_code}"
                    )
                elif os.WIFSIGNALED(status):
                    signal_num = os.WTERMSIG(status)
                    logger.info(
                        f"Worker [{pid}] was killed by signal {signal_num}"
                    )
                else:
                    logger.info(
                        f"Worker [{pid}] finished with unknown status {status}"
                    )
            except ChildProcessError:
                break
            except Exception as e:
                logger.exception(f"Error while reaping child process: {e}")
                break
