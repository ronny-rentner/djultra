import array
import io
import http.cookies
import json
import shlex
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from .management.commands import fastmanage_daemon
from .middleware import PatchMorselMiddleware


class RecvmsgConnection:
    def __init__(self, msg, ancillary=()):
        self.msg = msg
        self.ancillary = ancillary

    def recvmsg(self, size, ancillary_size):
        return self.msg, list(self.ancillary), 0, None


class RecordingConnection:
    def __init__(self):
        self.payloads = []
        self.closed = False

    def sendall(self, payload):
        self.payloads.append(payload)

    def close(self):
        self.closed = True


class FlushRecorder(io.StringIO):
    def __init__(self):
        super().__init__()
        self.flushed = False

    def flush(self):
        self.flushed = True
        super().flush()


def fastmanage_payload(env, argv):
    return json.dumps(env).encode() + b"\n" + (shlex.join(argv) + "\n").encode()


def fd_ancillary(*fds):
    return [
        (
            fastmanage_daemon.socket.SOL_SOCKET,
            fastmanage_daemon.socket.SCM_RIGHTS,
            array.array("i", fds).tobytes(),
        )
    ]


class FastmanageDaemonFunctionTests(TestCase):
    def parse_request(self, msg, ancillary=()):
        return object.__new__(fastmanage_daemon.FastmanageDaemon).parse_request(
            RecvmsgConnection(msg, ancillary)
        )

    def assert_parse_request_logs_error(self, msg, ancillary=()):
        with self.assertLogs(fastmanage_daemon.__name__, level="ERROR"):
            self.assertIsNone(self.parse_request(msg, ancillary))

    def run_worker_with_system_exit(self, code):
        calls = []

        class ExitManagementUtility:
            def execute(self, *args, **kwargs):
                calls.append((args, kwargs))
                raise SystemExit(code)

        conn = RecordingConnection()
        stdout = FlushRecorder()
        stderr = FlushRecorder()
        original_argv = fastmanage_daemon.sys.argv

        try:
            with mock.patch.object(fastmanage_daemon.mgmt, "ManagementUtility", ExitManagementUtility):
                with mock.patch.object(fastmanage_daemon.os, "dup2") as dup2:
                    with mock.patch.object(fastmanage_daemon.os, "close") as close:
                        with mock.patch.object(fastmanage_daemon.sys, "stdout", stdout):
                            with mock.patch.object(fastmanage_daemon.sys, "stderr", stderr):
                                with mock.patch.dict(fastmanage_daemon.os.environ, {}, clear=False):
                                    object.__new__(fastmanage_daemon.FastmanageDaemon).run_worker(
                                        conn,
                                        {},
                                        ["manage.py", "fake"],
                                        [101, 102, 103],
                                    )
        finally:
            fastmanage_daemon.sys.argv = original_argv

        return conn, stdout, stderr, dup2, close, calls

    def test_daemon_uses_default_socket_path_when_socket_setting_is_omitted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings():
                daemon = fastmanage_daemon.FastmanageDaemon(base_dir=temp_dir)

        self.assertEqual(daemon.sock_path, Path(temp_dir) / "fastmanage.sock")

    def test_daemon_rejects_explicit_none_socket_setting(self):
        with override_settings(DJU_DEV_FASTMANAGE_DAEMON_SOCKET=None):
            with self.assertRaises(ImproperlyConfigured):
                fastmanage_daemon.FastmanageDaemon()

    def test_daemon_uses_explicit_socket_path_setting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            socket_path = Path(temp_dir) / "custom-fastmanage.sock"
            with override_settings(DJU_DEV_FASTMANAGE_DAEMON_SOCKET=str(socket_path)):
                daemon = fastmanage_daemon.FastmanageDaemon()

        self.assertEqual(daemon.sock_path, socket_path)

    def test_parse_request_preserves_quoted_argv_and_stdio_fds(self):
        env = {"PWD": "/tmp/project", "FASTMANAGE_TEST": "quoted argv"}
        argv = ["manage.py", "shell", "-c", "print('fastmanage ok')"]

        parsed_env, parsed_argv, fds = self.parse_request(
            fastmanage_payload(env, argv),
            fd_ancillary(10, 11, 12),
        )

        self.assertEqual(parsed_env, env)
        self.assertEqual(parsed_argv, argv)
        self.assertEqual(fds, [10, 11, 12])

    def test_parse_request_rejects_worker_requests(self):
        result = self.parse_request(
            fastmanage_payload({fastmanage_daemon.ENV_WORKER: "1"}, ["manage.py", "check"]),
            fd_ancillary(10, 11, 12),
        )

        self.assertIsNone(result)

    def test_parse_request_rejects_missing_separator(self):
        self.assert_parse_request_logs_error(b'{"PWD": "/tmp/project"}', fd_ancillary(10, 11, 12))

    def test_parse_request_rejects_invalid_json(self):
        self.assert_parse_request_logs_error(b"{invalid json}\nmanage.py check\n", fd_ancillary(10, 11, 12))

    def test_parse_request_rejects_empty_command(self):
        self.assert_parse_request_logs_error(json.dumps({}).encode() + b"\n", fd_ancillary(10, 11, 12))

    def test_parse_request_rejects_missing_stdio_fds(self):
        self.assert_parse_request_logs_error(fastmanage_payload({}, ["manage.py", "check"]))

    def test_run_worker_sends_integer_system_exit_status(self):
        conn, stdout, stderr, dup2, close, calls = self.run_worker_with_system_exit(23)

        self.assertEqual(conn.payloads, [b"23\n"])
        self.assertTrue(conn.closed)
        self.assertTrue(stdout.flushed)
        self.assertTrue(stderr.flushed)
        dup2.assert_has_calls([mock.call(101, 0), mock.call(102, 1), mock.call(103, 2)])
        close.assert_has_calls([mock.call(101), mock.call(102), mock.call(103)])
        self.assertEqual(calls, [((), {"use_socket": False})])

    def test_run_worker_sends_zero_for_system_exit_none(self):
        conn, stdout, stderr, dup2, close, calls = self.run_worker_with_system_exit(None)

        self.assertEqual(conn.payloads, [b"0\n"])
        self.assertTrue(conn.closed)
        self.assertTrue(stdout.flushed)
        self.assertTrue(stderr.flushed)
        dup2.assert_has_calls([mock.call(101, 0), mock.call(102, 1), mock.call(103, 2)])
        close.assert_has_calls([mock.call(101), mock.call(102), mock.call(103)])
        self.assertEqual(calls, [((), {"use_socket": False})])

    def test_run_worker_prints_string_system_exit_and_sends_status_one(self):
        conn, stdout, stderr, dup2, close, calls = self.run_worker_with_system_exit("command failed")

        self.assertEqual(conn.payloads, [b"1\n"])
        self.assertEqual(stderr.getvalue(), "command failed\n")
        self.assertTrue(conn.closed)
        self.assertTrue(stdout.flushed)
        self.assertTrue(stderr.flushed)
        dup2.assert_has_calls([mock.call(101, 0), mock.call(102, 1), mock.call(103, 2)])
        close.assert_has_calls([mock.call(101), mock.call(102), mock.call(103)])
        self.assertEqual(calls, [((), {"use_socket": False})])


class PatchMorselMiddlewareTests(TestCase):
    def test_forces_cookie_settings_without_warning_for_django_defaults(self):
        with override_settings():
            with mock.patch("djultra.middleware.logger.warning") as warning:
                PatchMorselMiddleware(lambda request: None)

            self.assertEqual(settings.SESSION_COOKIE_SECURE, True)
            self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "None")
            self.assertEqual(settings.CSRF_COOKIE_SECURE, True)
            self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "None")
            warning.assert_not_called()

    def test_warns_before_overriding_conflicting_cookie_settings(self):
        with override_settings(
            SESSION_COOKIE_SECURE=False,
            SESSION_COOKIE_SAMESITE="Lax",
            CSRF_COOKIE_SECURE=False,
            CSRF_COOKIE_SAMESITE="Lax",
        ):
            with self.assertLogs("djultra.middleware", level="WARNING") as logs:
                PatchMorselMiddleware(lambda request: None)

            self.assertEqual(settings.SESSION_COOKIE_SECURE, True)
            self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "None")
            self.assertEqual(settings.CSRF_COOKIE_SECURE, True)
            self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "None")
            self.assertEqual(len(logs.output), 4)
            self.assertIn("SESSION_COOKIE_SECURE=True", logs.output[0])
            self.assertIn("overriding configured value False", logs.output[0])

    def test_patch_morsel_sets_partitioned_on_new_cookies(self):
        with override_settings():
            PatchMorselMiddleware(lambda request: None)

            cookie = http.cookies.SimpleCookie()
            cookie["csrftoken"] = "token"

            self.assertIn("Partitioned", cookie["csrftoken"].OutputString())
