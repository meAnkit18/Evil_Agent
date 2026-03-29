import os
import pty
import select
import signal
import subprocess
import threading
import time
from typing import Optional


class PTYTerminal:
    def __init__(self, shell: str = "/bin/bash", timeout: int = 30):
        self.shell = shell
        self.timeout = timeout
        self.sentinel = "__CMD_DONE__"

        self.master_fd: Optional[int] = None
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

        self._start_shell()

    def _start_shell(self):
        """Start persistent shell using PTY"""
        self.master_fd, slave_fd = pty.openpty()

        self.process = subprocess.Popen(
            [self.shell],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            universal_newlines=False,
            bufsize=0,
            preexec_fn=os.setsid  # allows killing entire process group
        )

        os.close(slave_fd)

        # small delay to stabilize shell
        time.sleep(0.2)
        self._flush_initial_output()

    def _flush_initial_output(self):
        """Clear initial shell noise"""
        try:
            while True:
                r, _, _ = select.select([self.master_fd], [], [], 0.05)
                if not r:
                    break
                os.read(self.master_fd, 1024)
        except Exception:
            pass

    def run(self, command: str) -> dict:
        """
        Execute command in persistent shell.
        Uses sentinel to detect true command completion.
        """
        with self._lock:
            if not self.process or self.process.poll() is not None:
                raise RuntimeError("Shell process is not running")

            # Inject sentinel after command to detect true completion
            full_command = f"{command.strip()}; echo {self.sentinel}\n"
            os.write(self.master_fd, full_command.encode())

            output = self._read_output()

            return {
                "status": "success",
                "command": command,
                "output": output.strip(),
            }

    def _read_output(self) -> str:
        """Read output until sentinel seen or timeout"""
        output = b""
        start_time = time.time()
        sentinel_bytes = self.sentinel.encode()

        while True:
            if time.time() - start_time > self.timeout:
                self._kill_process_group()
                return output.decode(errors="ignore") + "\n[ERROR] Command timed out"

            r, _, _ = select.select([self.master_fd], [], [], 0.1)

            if r:
                try:
                    chunk = os.read(self.master_fd, 4096)
                    if not chunk:
                        break
                    output += chunk

                    # Only break when sentinel is found → command truly finished
                    if sentinel_bytes in output:
                        break
                except OSError:
                    break
            else:
                # No data yet — keep waiting (don't exit prematurely)
                continue

        decoded = output.decode(errors="ignore")
        # Clean up sentinel from output
        return decoded.replace(self.sentinel, "").strip()

    def _kill_process_group(self):
        """Kill all child processes"""
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except Exception:
                pass

    def close(self):
        """Cleanup terminal"""
        try:
            if self.process:
                self._kill_process_group()
                self.process.terminate()
                self.process.wait(timeout=2)
        except Exception:
            pass

        try:
            if self.master_fd:
                os.close(self.master_fd)
        except Exception:
            pass