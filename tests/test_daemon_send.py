# SPDX-FileCopyrightText: Copyright (C) 2026 Bruce Ashfield
#
# SPDX-License-Identifier: MIT
"""
Tests for how vrunner.sh gets an answer from the memory resident guest: each
command gets its own answer and exit code, however long it takes and whatever
happened to the command before it.

    pytest tests/test_daemon_send.py -v --vdkr-dir /tmp/vcontainer
"""

import os
import signal
import subprocess
import time

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.memres]

# Each tool's memres fixture, and how vrunner.sh knows its guest
TOOLS = {"vdkr": ("memres_session", "docker"), "vpdmn": ("vpdmn_memres_session", "podman")}


class Guest:
    def __init__(self, tool, runner, runtime):
        self.runner = runner
        self.command = [
            str(runner.binary.parent / "vrunner.sh"),
            "--runtime", runtime,
            "--arch", runner.arch,
            "--blob-dir", str(runner.binary.parent / f"{tool}-blobs" / runner.arch),
            "--state-dir", str(runner.state_dir),
            "--daemon-send",
        ]

    def env(self, limit):
        env = dict(self.runner.env)
        env.pop("VCONTAINER_SEND_TIMEOUT", None)
        if limit:
            env["VCONTAINER_SEND_TIMEOUT"] = str(limit)
        return env

    def send(self, shell_command, limit=None, timeout=120):
        return subprocess.run(self.command + [shell_command], env=self.env(limit), text=True,
                              capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)

    def start(self, shell_command):
        return subprocess.Popen(self.command + [shell_command], env=self.env(None), text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)


@pytest.fixture(params=TOOLS)
def guest(request):
    fixture, runtime = TOOLS[request.param]
    runner = request.getfixturevalue(fixture)
    runner.ensure_memres()
    guest = Guest(request.param, runner, runtime)
    # What the test before this one left behind would be waited for, and count
    # against a time limit
    guest.send("true")
    return guest


class TestDaemonSend:
    def test_exit_code(self, guest):
        result = guest.send("echo here; (exit 5)")
        assert result.returncode == 5
        assert "here" in result.stdout

    def test_output_without_a_final_newline(self, guest):
        result = guest.send("printf no-newline")
        assert result.returncode == 0
        assert result.stdout == "no-newline\n"

    def test_no_limit_by_default(self, guest):
        result = guest.send("sleep 65; echo finished; (exit 6)", timeout=200)
        assert result.returncode == 6
        assert "finished" in result.stdout

    def test_time_limit_is_reported(self, guest):
        result = guest.send("sleep 8; echo first", limit=2)
        assert result.returncode == 124
        assert "No answer from the guest in 2s" in result.stderr
        assert "first" not in result.stdout

    def test_answers_after_a_time_limit(self, guest):
        guest.send("sleep 12; echo first", limit=2)
        started = time.monotonic()
        result = guest.send("echo second; (exit 3)")
        assert "first" not in result.stdout
        assert "second" in result.stdout
        assert result.returncode == 3
        assert time.monotonic() - started > 2, "should wait for the command left behind"
        assert "Waiting for an earlier command" in result.stderr
        assert guest.send("echo third").stdout.strip() == "third"

    def test_answers_after_an_interrupted_client(self, guest):
        client = guest.start("sleep 8; echo first")
        time.sleep(2)
        os.killpg(client.pid, signal.SIGKILL)
        client.communicate()
        result = guest.send("echo second")
        assert result.returncode == 0
        assert "first" not in result.stdout
        assert "second" in result.stdout

    def test_guest_going_away_is_reported(self, guest):
        client = guest.start("sleep 60; echo finished")
        try:
            time.sleep(3)
            pid = int((guest.runner.state_dir / "daemon.pid").read_text())
            os.kill(pid, signal.SIGKILL)
            output, _ = client.communicate(timeout=30)
            assert client.returncode == 1, output
            assert "Lost the connection" in output
        finally:
            client.kill()
            guest.runner.ensure_memres()
