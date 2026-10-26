import subprocess
import time
from threading import Event
from typing import Optional, Sequence

from cancellation import CancellationRequested


def run_process(cmd: Sequence[str], *, cancel_event: Optional[Event] = None,
               timeout: Optional[float] = None, **kwargs) -> subprocess.CompletedProcess:
    """Run a child process that can be stopped by a pipeline cancellation request."""
    check = kwargs.pop("check", False)
    if cancel_event is None:
        return subprocess.run(cmd, timeout=timeout, check=check, **kwargs)
    if cancel_event.is_set():
        raise CancellationRequested()

    if kwargs.pop("capture_output", False):
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.PIPE)
    proc = subprocess.Popen(cmd, **kwargs)
    deadline = time.monotonic() + timeout if timeout is not None else None
    stdout = stderr = None
    try:
        while True:
            if cancel_event.is_set():
                if proc.poll() is None:
                    try:
                        proc.terminate()
                    except OSError:
                        pass
                try:
                    stdout, stderr = proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                raise CancellationRequested()
            try:
                stdout, stderr = proc.communicate(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                if deadline is not None and time.monotonic() >= deadline:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                    raise subprocess.TimeoutExpired(cmd, timeout, output=stdout, stderr=stderr)

        result = subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
        if check and result.returncode:
            raise subprocess.CalledProcessError(result.returncode, cmd, output=stdout, stderr=stderr)
        return result
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
