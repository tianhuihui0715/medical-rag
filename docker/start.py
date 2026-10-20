"""在一个容器中管理 API 和队列；模型接口就绪后消费任务，退出时先停止消费者。"""

import os
import signal
import subprocess
import sys
import time
from threading import Event
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    stopping = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopping.set())
    processes: list[subprocess.Popen] = []
    try:
        api = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0",
            "--port", "8000", "--workers", "1",
        ], start_new_session=True)
        processes.append(api)
        deadline = time.monotonic() + 300
        while not stopping.is_set():
            if api.poll() is not None:
                return api.returncode or 1
            try:
                with urlopen("http://127.0.0.1:8000/openapi.json", timeout=2):
                    break
            except (URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    print("模型接口启动超时，停止应用", flush=True)
                    return 1
                stopping.wait(1)
        if stopping.is_set():
            return 0
        worker = subprocess.Popen(
            [sys.executable, "-m", "task.parse_queue"], start_new_session=True,
        )
        processes.append(worker)
        while not stopping.wait(1):
            for process in processes:
                if process.poll() is not None:
                    print("应用子进程退出，停止整个容器", flush=True)
                    return process.returncode or 1
        return 0
    finally:
        # 先等待队列当前任务结束，再关闭它依赖的本地模型接口；超时后清理进程组。
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


if __name__ == "__main__":
    sys.exit(main())
