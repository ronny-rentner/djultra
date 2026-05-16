import array
import importlib
import json
import os
import shlex
import socket
import sys
import tempfile
from unittest import TestCase, mock

from .management.commands import fastmanage_daemon


def close_fds(fds):
    for fd in fds:
        os.close(fd)


def read_fd(fd):
    chunks = []
    while True:
        chunk = os.read(fd, 4096)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


class FastmanageProtocolTests(TestCase):
    def test_parse_request_preserves_quoted_argv_and_stdio_fds(self):
        client, daemon = socket.socketpair()
        stdin_read, stdin_write = os.pipe()
        stdout_read, stdout_write = os.pipe()
        stderr_read, stderr_write = os.pipe()
        sent_fds = [stdin_read, stdout_write, stderr_write]
        received_fds = []

        try:
            env = {"PWD": os.getcwd(), "FASTMANAGE_TEST": "quoted argv"}
            argv = ["manage.py", "shell", "-c", "print('fastmanage ok')"]
            payload = json.dumps(env).encode() + b"\n" + (shlex.join(argv) + "\n").encode()
            ancillary = [
                (
                    socket.SOL_SOCKET,
                    socket.SCM_RIGHTS,
                    array.array("i", sent_fds).tobytes(),
                )
            ]

            client.sendmsg([payload], ancillary)
            daemon_instance = object.__new__(fastmanage_daemon.FastmanageDaemon)
            parsed_env, parsed_argv, received_fds = daemon_instance.parse_request(daemon)

            self.assertEqual(parsed_env["FASTMANAGE_TEST"], "quoted argv")
            self.assertEqual(parsed_argv, argv)
            self.assertEqual(len(received_fds), 3)
        finally:
            client.close()
            daemon.close()
            close_fds([stdin_read, stdin_write, stdout_read, stdout_write, stderr_read, stderr_write])
            close_fds(received_fds)

    def test_worker_writes_to_passed_stdout_and_stderr_without_status_payload(self):
        class OutputManagementUtility:
            def execute(self, *args, **kwargs):
                print("fastmanage stdout")
                print("fastmanage stderr", file=sys.stderr)
                raise SystemExit(23)

        parent_conn, child_conn = socket.socketpair()
        stdin_read, stdin_write = os.pipe()
        stdout_read, stdout_write = os.pipe()
        stderr_read, stderr_write = os.pipe()

        pid = os.fork()
        if pid == 0:
            try:
                parent_conn.close()
                close_fds([stdin_write, stdout_read, stderr_read])
                daemon_instance = object.__new__(fastmanage_daemon.FastmanageDaemon)
                with mock.patch.object(fastmanage_daemon.mgmt, "ManagementUtility", OutputManagementUtility):
                    daemon_instance.run_worker(
                        child_conn,
                        {"PWD": os.getcwd()},
                        ["manage.py", "fake"],
                        [stdin_read, stdout_write, stderr_write],
                    )
                os._exit(0)
            except BaseException as exc:
                os.write(2, f"fastmanage child test failed: {exc}\n".encode())
                os._exit(99)

        child_conn.close()
        close_fds([stdin_read, stdout_write, stderr_write])

        try:
            socket_payload = parent_conn.recv(4096)
            _, status = os.waitpid(pid, 0)
            stdout_output = read_fd(stdout_read).decode()
            stderr_output = read_fd(stderr_read).decode()
        finally:
            parent_conn.close()
            close_fds([stdin_write, stdout_read, stderr_read])

        self.assertEqual(socket_payload, b"")
        self.assertEqual(stdout_output, "fastmanage stdout\n")
        self.assertEqual(stderr_output, "fastmanage stderr\n")
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)

    def test_missing_socket_falls_back_to_django_management_utility(self):
        import django.core.management as django_management

        module_name = "djultra.management.commands.fastmanage_patch"
        module_was_loaded = module_name in sys.modules
        management_utility_before_import = django_management.ManagementUtility
        fastmanage_patch = importlib.import_module(module_name)
        self.addCleanup(setattr, django_management, "ManagementUtility", management_utility_before_import)
        if not module_was_loaded:
            self.addCleanup(sys.modules.pop, module_name, None)

        fallback_calls = []
        django_management_utility = fastmanage_patch.SocketManagementUtility.__mro__[1]

        def execute_without_socket(utility, *args, **kwargs):
            fallback_calls.append((utility.argv, args, kwargs))
            return "fallback-result"

        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                with mock.patch.object(django_management_utility, "execute", execute_without_socket):
                    result = fastmanage_patch.SocketManagementUtility(["manage.py", "check"]).execute()
            finally:
                os.chdir(original_cwd)

        self.assertEqual(result, "fallback-result")
        self.assertEqual(fallback_calls, [(["manage.py", "check"], (), {})])
