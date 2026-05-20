import os
import subprocess
import threading
import sys
import re
from typing import Dict, Any, List, Optional

class ScraperManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ScraperManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.process: Optional[subprocess.Popen] = None
        self.active_phase: Optional[str] = None  # None, "phase1", "phase2", "phase3", "phase4"
        self.status: str = "idle"  # "idle", "running", "completed", "failed", "cancelled"
        self.logs: List[str] = []
        self.progress_total: int = 0
        self.progress_current: int = 0
        self.progress_percent: float = 0.0
        self.lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            # Check if process is still running
            if self.process and self.process.poll() is not None:
                # Process finished
                exit_code = self.process.poll()
                if exit_code == 0:
                    self.status = "completed"
                elif self.status == "running":
                    self.status = "failed"
                self.active_phase = None
                self.process = None
                
            return {
                "phase": self.active_phase,
                "status": self.status,
                "progress": {
                    "total": self.progress_total,
                    "current": self.progress_current,
                    "percent": round(self.progress_percent, 2)
                }
            }

    def get_logs(self, limit: int = 500) -> List[str]:
        with self.lock:
            return self.logs[-limit:]

    def clear_logs(self):
        with self.lock:
            self.logs = []

    def stop_scraping(self) -> bool:
        with self.lock:
            if not self.process or self.status != "running":
                return False
                
            try:
                # Terminate subprocess and descendants
                self.process.terminate()
                self.process.wait(timeout=3)
                self.status = "cancelled"
                self.active_phase = None
                self.process = None
                self.logs.append("[!] Scraping task was manually cancelled by the user.\n")
                return True
            except Exception as e:
                self.logs.append(f"[!] Error cancelling process: {e}\n")
                try:
                    self.process.kill()
                    self.process = None
                    self.status = "cancelled"
                    self.active_phase = None
                except Exception:
                    pass
                return True

    def start_phase(self, phase: str) -> bool:
        with self.lock:
            if self.process and self.process.poll() is None:
                # Process is already running
                return False

            self.status = "running"
            self.active_phase = phase
            self.progress_total = 0
            self.progress_current = 0
            self.progress_percent = 0.0
            
            # Map phases to script names
            scripts = {
                "phase1": "scraper.py",
                "phase2": "parse_responses.py",
                "phase3": "scrape_all_schedules.py",
                "phase4": "parse_schedules_to_db.py"
            }
            
            script_name = scripts.get(phase)
            if not script_name:
                self.status = "idle"
                self.active_phase = None
                return False
                
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            script_path = os.path.join(backend_dir, script_name)
            
            self.logs.append(f"\n[>] Starting Phase: {phase.upper()} ({script_name})...\n")
            
            # Run the process
            env = os.environ.copy()
            env["AUTO_CONFIRM"] = "1"  # Bypass prompts in scraper.py
            env["PYTHONUNBUFFERED"] = "1"  # Disable python print buffer to get real-time stdout
            
            try:
                # Use current virtual environment's python or standard python
                python_exe = sys.executable
                self.process = subprocess.Popen(
                    [python_exe, script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=backend_dir,
                    env=env
                )
                
                # Start logging thread
                self.thread = threading.Thread(target=self._log_reader_loop, args=(phase,))
                self.thread.daemon = True
                self.thread.start()
                return True
            except Exception as e:
                self.status = "failed"
                self.active_phase = None
                self.logs.append(f"[!] Failed to launch scraping subprocess: {e}\n")
                return False

    def _log_reader_loop(self, phase: str):
        proc = self.process
        if not proc or not proc.stdout:
            return

        # Regular expressions to parse progress
        # Match progress formats in scrape_all_schedules:
        # Progress: 140/320 (Success: 100, Skipped: 40)
        progress_re = re.compile(r"Progress:\s*(\d+)/(\d+)")
        
        # Match progress formats in parse_schedules_to_db:
        # Progress: 400/1200 files parsed
        parse_progress_re = re.compile(r"Progress:\s*(\d+)/(\d+)\s+files")

        for line in proc.stdout:
            cleaned_line = line.strip()
            
            # Parse progress metrics if applicable
            m = progress_re.search(cleaned_line) or parse_progress_re.search(cleaned_line)
            if m:
                current = int(m.group(1))
                total = int(m.group(2))
                with self.lock:
                    self.progress_current = current
                    self.progress_total = total
                    if total > 0:
                        self.progress_percent = (current / total) * 100.0

            # Store the log line
            with self.lock:
                # If the line ends with \r (carriage return), we don't necessarily want thousands of progress lines
                # but for simplicity, we just keep the last 2000 log entries
                self.logs.append(line)
                if len(self.logs) > 5000:
                    self.logs.pop(0)

        # Wait for the process to exit completely
        exit_code = proc.wait()
        
        with self.lock:
            if self.process == proc:  # Ensure we are editing state of the same process
                if exit_code == 0:
                    self.status = "completed"
                    self.progress_percent = 100.0
                    self.logs.append(f"\n[+] Phase {phase.upper()} completed successfully!\n")
                else:
                    self.status = "failed"
                    self.logs.append(f"\n[!] Phase {phase.upper()} exited with error code {exit_code}.\n")
                self.active_phase = None
                self.process = None

# Singleton access
scraper_manager = ScraperManager()
