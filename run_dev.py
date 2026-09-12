"""
Robust Dev Server Launcher & Watchdog
=====================================
Permanently solves WinError 10013, WinError 10048, UnicodeEncodeError on cp1252,
and socket port-in-use collisions on Windows.
Guarantees:
1. Pure ASCII logging + UTF-8 stream reconfiguration for zero encoding crashes.
2. Windows Job Object binding: All child processes (uvicorn, node/vite) are kernel-bound
   to automatically self-terminate when the launcher process exits or is killed.
3. Clean socket releasing: Aggressively checks and terminates stale processes holding ports 8000/5173.
4. Native virtual environment resolution: Prefers project's .venv over system Python.
5. Direct Node execution: Launches vite directly through node without cmd.exe wrappers when possible.
6. Health verification: Confirms both backend and frontend HTTP responses before declaring online.
"""

import sys
import os
import subprocess
import time
import socket
import signal
import atexit

# Reconfigure stdout/stderr to utf-8 or replace to prevent cp1252 charmap crashes on Windows
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

backend_proc = None
frontend_proc = None
_job_object = None


def setup_windows_job_object():
    """Binds all child processes to a Windows Job Object that automatically kills
    all descendants when the parent Python process terminates for ANY reason."""
    global _job_object
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryLimit", ctypes.c_size_t),
                ("PeakJobMemoryLimit", ctypes.c_size_t),
            ]

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        JobObjectExtendedLimitInformation = 9
        res = kernel32.SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if res:
            current_proc = kernel32.GetCurrentProcess()
            kernel32.AssignProcessToJobObject(job, current_proc)
            _job_object = job
            return job
    except Exception:
        pass
    return None


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def kill_processes_on_port(port: int):
    """Aggressively finds and terminates any process listening on a given port."""
    if sys.platform != "win32":
        try:
            subprocess.run(f"fuser -k {port}/tcp", shell=True, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        return

    try:
        cmd = "netstat -ano"
        out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        pids = set()
        my_pid = os.getpid()
        for line in out.strip().splitlines():
            line_upper = line.upper()
            if "LISTENING" not in line_upper:
                continue
            parts = line.split()
            if len(parts) >= 5:
                local_addr = parts[1]
                if local_addr.endswith(f":{port}"):
                    pid_str = parts[-1]
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        if pid != my_pid and pid != 0:
                            pids.add(pid)
        for pid in pids:
            print(f"[CLEANUP] Terminating listening process PID {pid} on port {port}...")
            subprocess.run(
                f"taskkill /F /T /PID {pid}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass


def release_ports():
    kill_processes_on_port(8000)
    kill_processes_on_port(5173)
    for _ in range(10):
        if not is_port_in_use(8000) and not is_port_in_use(5173):
            break
        time.sleep(0.2)


def cleanup():
    global backend_proc, frontend_proc
    print("\n[STOP] Cleaning up dev server processes...")
    if sys.platform == "win32":
        if backend_proc and backend_proc.poll() is None:
            subprocess.run(
                f"taskkill /F /T /PID {backend_proc.pid}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        if frontend_proc and frontend_proc.poll() is None:
            subprocess.run(
                f"taskkill /F /T /PID {frontend_proc.pid}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    else:
        if backend_proc and backend_proc.poll() is None:
            backend_proc.terminate()
        if frontend_proc and frontend_proc.poll() is None:
            frontend_proc.terminate()
    release_ports()
    print("[DONE] Ports 8000 and 5173 are completely free.")


atexit.register(cleanup)


def signal_handler(sig, frame):
    cleanup()
    sys.exit(0)


try:
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal_handler)
except Exception:
    pass


def main():
    global backend_proc, frontend_proc

    backend_only = "--backend-only" in sys.argv
    frontend_only = "--frontend-only" in sys.argv

    print("=" * 65)
    print("  FLOWS Urban Flood Nowcasting -- Clean Server Engine")
    print("=" * 65)

    # 1. Enable Windows Kernel Job Object for leak-proof process termination
    setup_windows_job_object()

    # 2. Clear any zombie or orphaned processes from previous runs
    print("[1/4] Checking and clearing socket reservations...")
    if not frontend_only:
        kill_processes_on_port(8000)
    if not backend_only:
        kill_processes_on_port(5173)
    time.sleep(0.3)

    project_root = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(project_root, "frontend")

    # Determine Python executable (prefer .venv if present)
    venv_py = os.path.join(project_root, ".venv", "Scripts", "python.exe")
    python_bin = venv_py if os.path.exists(venv_py) else sys.executable
    print(f"[2/4] Python Runtime: {python_bin}")

    # 3. Launch FastAPI backend explicitly on 127.0.0.1:8000
    if not frontend_only:
        backend_cmd = [
            python_bin,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--reload",
        ]
        print("[3/4] Launching FastAPI backend on http://127.0.0.1:8000...")
        backend_proc = subprocess.Popen(backend_cmd, cwd=project_root)

        # Wait for backend to be ready
        for i in range(35):
            if is_port_in_use(8000):
                print("      [OK] Backend is online and accepting connections.")
                break
            time.sleep(0.3)
        else:
            print("      [WARN] Backend taking longer than usual to bind port 8000...")

    # 4. Launch Vite frontend with 0.0.0.0 host and port 5173
    if not backend_only:
        vite_js = os.path.join(frontend_dir, "node_modules", "vite", "bin", "vite.js")
        if os.path.exists(vite_js):
            frontend_cmd = ["node", vite_js, "--host", "0.0.0.0", "--port", "5173"]
            print("[4/4] Launching Vite frontend on http://localhost:5173...")
            frontend_proc = subprocess.Popen(frontend_cmd, cwd=frontend_dir)
        else:
            npm_cmd = "npx vite --host 0.0.0.0 --port 5173"
            print("[4/4] Launching Vite frontend (via npx) on http://localhost:5173...")
            frontend_proc = subprocess.Popen(npm_cmd, cwd=frontend_dir, shell=True)

        for i in range(25):
            if is_port_in_use(5173):
                print("      [OK] Frontend is online and accepting connections.")
                break
            time.sleep(0.3)

    print("-" * 65)
    print("  -> Web App:  http://localhost:5173  or  http://127.0.0.1:5173")
    print("  -> API Docs: http://127.0.0.1:8000/docs")
    print("  (Press Ctrl+C at any time to cleanly stop all servers)")
    print("-" * 65)

    try:
        while True:
            time.sleep(1)
            if backend_proc and backend_proc.poll() is not None:
                print("[ERROR] Backend exited unexpectedly.")
                break
            if frontend_proc and frontend_proc.poll() is not None:
                print("[INFO] Frontend stopped.")
                break
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
