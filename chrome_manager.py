"""Chrome Debugging Port Auto-Management Module."""

import asyncio
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import requests

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger("chrome_manager")

# Config from environment
CHROME_DEBUG_PORT = int(os.getenv("CHROME_DEBUG_PORT", "9222"))
# Use a dedicated subdirectory for scraping to avoid "non-default data directory" error
CHROME_USER_DATA_DIR = os.getenv(
    "CHROME_USER_DATA_DIR",
    str(Path(os.getenv("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data" / "ScrapingProfile")
)
CHROME_PATH = os.getenv(
    "CHROME_PATH",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
)
CHROME_START_TIMEOUT = float(os.getenv("CHROME_START_TIMEOUT", "15.0"))
CHROME_MANAGER_LOG_LEVEL = os.getenv("CHROME_MANAGER_LOG_LEVEL", "INFO").upper()

logger.setLevel(getattr(logging, CHROME_MANAGER_LOG_LEVEL, logging.INFO))

_chrome_process: Optional[asyncio.subprocess.Process] = None
_chrome_pid: Optional[int] = None


def _find_chrome_executable() -> str:
    """Find Chrome executable path."""
    candidates = [
        CHROME_PATH,
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    # Try to find via registry or where
    try:
        result = subprocess.run(
            ["where", "chrome"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except Exception:
        pass
    raise FileNotFoundError("Chrome executable not found. Set CHROME_PATH environment variable.")


async def _is_chrome_debugging_alive(port: int) -> bool:
    """Check if Chrome debugging port is responding."""
    try:
        resp = await asyncio.to_thread(
            requests.get,
            f"http://127.0.0.1:{port}/json/version",
            timeout=2
        )
        return resp.status_code == 200
    except Exception:
        return False


async def _verify_chrome_pid(port: int, expected_pid: int) -> bool:
    """Verify that the process listening on the debugging port matches expected PID."""
    if not PSUTIL_AVAILABLE:
        logger.debug("psutil not available, skipping PID verification")
        return True
    
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr.port == port and conn.status == "LISTEN":
                if conn.pid == expected_pid:
                    logger.debug(f"PID verification passed: port {port} -> PID {expected_pid}")
                    return True
                else:
                    logger.warning(f"PID mismatch on port {port}: expected {expected_pid}, got {conn.pid}")
                    return False
    except Exception as e:
        logger.debug(f"PID verification error: {e}")
    return True


async def _wait_for_debugging_port(port: int, timeout: float) -> None:
    """Wait for Chrome debugging port to become ready."""
    deadline = asyncio.get_event_loop().time() + timeout
    attempt = 0
    
    while asyncio.get_event_loop().time() < deadline:
        attempt += 1
        if await _is_chrome_debugging_alive(port):
            logger.info(f"Chrome debugging port {port} ready (attempt {attempt})")
            return
        
        remaining = deadline - asyncio.get_event_loop().time()
        logger.debug(f"Waiting for Chrome debugging port {port}... ({remaining:.1f}s remaining)")
        await asyncio.sleep(0.5)
    
    raise TimeoutError(f"Chrome debugging port {port} not ready after {timeout}s")


async def ensure_chrome_debugging(
    port: int = CHROME_DEBUG_PORT,
    user_data_dir: Optional[str] = None,
    chrome_path: Optional[str] = None,
    timeout: float = CHROME_START_TIMEOUT
) -> Optional[int]:
    """
    Ensure Chrome debugging port is active.
    Returns PID of launched Chrome process, or None if already running.
    """
    global _chrome_process, _chrome_pid
    
    user_data_dir = user_data_dir or CHROME_USER_DATA_DIR
    chrome_path = chrome_path or _find_chrome_executable()
    
    logger.info(f"Checking Chrome debugging on port {port}...")
    
    # Check if already running
    if await _is_chrome_debugging_alive(port):
        logger.info(f"Chrome debugging already active on port {port}")
        return None
    
    logger.info(f"Starting Chrome with debugging on port {port}...")
    logger.debug(f"Chrome path: {chrome_path}")
    logger.debug(f"User data dir: {user_data_dir}")
    
    # Prepare Chrome arguments - add explicit URL to open
    chrome_args = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--start-maximized",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "https://www.mercadolibre.com.mx",  # Explicitly open MercadoLibre
    ]
    
    # Capture stderr to a temp file for debugging
    import tempfile
    stderr_file = tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False, prefix='chrome_stderr_')
    stderr_path = stderr_file.name
    stderr_file.close()
    
    logger.debug(f"Chrome stderr will be logged to: {stderr_path}")
    logger.debug(f"Chrome args: {' '.join(chrome_args)}")
    
    try:
        # Start Chrome as subprocess
        _chrome_process = await asyncio.create_subprocess_exec(
            *chrome_args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=open(stderr_path, 'w'),
        )
        _chrome_pid = _chrome_process.pid
        logger.info(f"Chrome launched with PID {_chrome_pid}")
        
        # Wait for debugging port to be ready
        await _wait_for_debugging_port(port, timeout)
        
        # Verify PID matches
        if not await _verify_chrome_pid(port, _chrome_pid):
            logger.error(f"PID verification failed for Chrome on port {port}")
            # Read stderr for debugging
            try:
                with open(stderr_path, 'r') as f:
                    stderr_content = f.read()
                if stderr_content:
                    logger.error(f"Chrome stderr: {stderr_content[:2000]}")
            except:
                pass
            await terminate_chrome_debugging()
            raise RuntimeError(f"Chrome started but PID verification failed on port {port}")
        
        logger.info(f"Chrome debugging ready on port {port} (PID: {_chrome_pid})")
        
        # Read and log stderr if any
        try:
            with open(stderr_path, 'r') as f:
                stderr_content = f.read()
            if stderr_content:
                logger.debug(f"Chrome stderr: {stderr_content[:1000]}")
        except:
            pass
        
        return _chrome_pid
        
    except TimeoutError:
        logger.error(f"Timeout: Chrome debugging port {port} not ready after {timeout}s")
        await terminate_chrome_debugging()
        raise
    except Exception as e:
        logger.exception(f"Failed to start Chrome debugging: {e}")
        await terminate_chrome_debugging()
        raise


async def terminate_chrome_debugging() -> None:
    """Terminate the Chrome process if we launched it."""
    global _chrome_process, _chrome_pid
    
    if _chrome_process is None:
        logger.debug("No Chrome process to terminate")
        return
    
    pid = _chrome_pid
    logger.info(f"Terminating Chrome debugging process (PID: {pid})...")
    
    try:
        if _chrome_process.returncode is None:
            _chrome_process.terminate()
            try:
                await asyncio.wait_for(_chrome_process.wait(), timeout=5.0)
                logger.info(f"Chrome process {pid} terminated gracefully")
            except asyncio.TimeoutError:
                logger.warning(f"Chrome process {pid} did not terminate gracefully, killing...")
                _chrome_process.kill()
                await _chrome_process.wait()
                logger.info(f"Chrome process {pid} killed")
        else:
            logger.debug(f"Chrome process {pid} already exited with code {_chrome_process.returncode}")
    except ProcessLookupError:
        logger.debug(f"Chrome process {pid} already gone")
    except Exception as e:
        logger.error(f"Error terminating Chrome process {pid}: {e}")
    finally:
        _chrome_process = None
        _chrome_pid = None


def get_chrome_pid() -> Optional[int]:
    """Get the PID of the managed Chrome process."""
    return _chrome_pid


def is_chrome_managed() -> bool:
    """Check if we are managing a Chrome process."""
    return _chrome_process is not None and _chrome_process.returncode is None