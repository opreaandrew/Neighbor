import os
import queue
import threading
import multiprocessing
import systemd.journal
from enum import Enum
from pathlib import Path
from datetime import datetime, timedelta
from ..base import LogSource, LogEvent, Severity

class TimePeriod(Enum):
    ALL = "all"
    BOOT = "boot"
    NOW = "now"
    CUSTOM = "custom"

def _map_priority_to_severity(priority):
    """Map systemd priority (0-7) to Severity enum."""
    if priority is None:
        return Severity.INFO
    elif priority <= 3:
        return Severity.ERROR
    elif priority == 4:
        return Severity.WARNING
    elif priority <= 6:
        return Severity.INFO
    else:
        return Severity.DEBUG

def _entry_to_dict(entry):
    """Convert a journal entry to a LogEvent dict."""
    msg = entry.get('MESSAGE')
    if not msg:
        return None
    
    if isinstance(msg, bytes):
        msg = msg.decode('utf-8', errors='replace')
    
    return {
        'source': 'systemd',
        'severity': _map_priority_to_severity(entry.get('PRIORITY')),
        'timestamp': entry.get('__REALTIME_TIMESTAMP'),
        'subsystem': entry.get('SYSLOG_IDENTIFIER') or entry.get('_SYSTEMD_UNIT') or 'unknown',
        'raw_message': msg,
        'structured_data': {k: v for k, v in entry.items() if isinstance(v, (str, int, float, bool))}
    }

def process_log_chunk(args):
    """Worker function to process a specific time range of logs."""
    # Lower priority of this worker process
    try:
        os.nice(10)
    except Exception:
        pass

    start_time, end_time = args
    events = []

    j = systemd.journal.Reader()
    try:
        j.seek_realtime(start_time)
    except Exception:
        return events

    for entry in j:
        timestamp = entry.get('__REALTIME_TIMESTAMP')
        if timestamp and timestamp > end_time:
            break

        ev_dict = _entry_to_dict(entry)
        if ev_dict:
            events.append(ev_dict)

    return events

class SystemdSource(LogSource):
    def __init__(self, core_allocation=1, time_period: TimePeriod = TimePeriod.ALL, custom_start_time: float = None):
        self.cpu_count = core_allocation if core_allocation > 0 else 1
        self.journal = None
        self.cursor = None
        
        self.time_period = time_period
        self.custom_start_time = custom_start_time
        
        # Thread-safe queue for historical events found by background workers
        self.history_queue = queue.Queue(maxsize=200)
        self.history_done = False
        
        # Define cursor path
        self.cursor_dir = Path(os.path.expanduser("~/.local/share/neighbor/cursors"))
        self.cursor_path = self.cursor_dir / "systemd_cursor.txt"

    def _get_scan_range(self, reader, time_period):
        """Determine start and end times for scanning based on time_period."""
        reader.seek_tail()
        last = reader.get_previous()
        abs_end_time = last.get('__REALTIME_TIMESTAMP') if last else datetime.now()
        
        if time_period == TimePeriod.ALL:
            reader.seek_head()
            first = reader.get_next()
            return first.get('__REALTIME_TIMESTAMP') if first else None, abs_end_time
                
        elif time_period == TimePeriod.BOOT:
            reader.this_boot()
            reader.seek_head()
            first = reader.get_next()
            return first.get('__REALTIME_TIMESTAMP') if first else None, abs_end_time
        
        elif time_period == TimePeriod.NOW:
            reader.seek_tail()
            last = reader.get_previous()
            return last.get('__REALTIME_TIMESTAMP') if last else None, abs_end_time

        elif time_period == TimePeriod.CUSTOM and self.custom_start_time:
            return datetime.fromtimestamp(self.custom_start_time), abs_end_time
            
        return None, None

    def _create_time_chunks(self, start_time, end_time):
        """Split time range into chunks for parallel processing."""
        total_duration = (end_time - start_time).total_seconds()
        
        if total_duration <= 5:
            return [(start_time, end_time)]
        
        chunk_size = total_duration / self.cpu_count
        chunks = []
        current = start_time
        
        for i in range(self.cpu_count):
            if i == self.cpu_count - 1:
                next_time = end_time + timedelta(seconds=1)
            else:
                next_time = current + timedelta(seconds=chunk_size)
            
            chunks.append((current, next_time))
            current = next_time
        
        return chunks

    def _scan_history_background(self, start_time, end_time):
        """Runs in a background thread. Manages the pool and pushes results to queue."""
        if not start_time or not end_time or start_time >= end_time:
            self.history_done = True
            return

        chunk_args = self._create_time_chunks(start_time, end_time)

        try:
            with multiprocessing.Pool(processes=self.cpu_count) as pool:
                for chunk_res in pool.imap_unordered(process_log_chunk, chunk_args):
                    for ev_dict in chunk_res:
                        try:
                            self.history_queue.put(LogEvent(**ev_dict))
                        except Exception as e:
                            print(f"Error reformating event: {e}")
        except Exception as e:
            print(f"Background scan error: {e}")
        finally:
            self.history_done = True

    def _load_cursor(self):
        """Load cursor from file if it exists."""
        if self.cursor_path.exists():
            with open(self.cursor_path, 'r') as f:
                return f.read().strip()
        return None

    def _initialize_journal_position(self, reader):
        """Position the journal reader based on cursor or at tail."""
        if self.cursor:
            try:
                reader.seek_cursor(self.cursor)
                return
            except Exception:
                pass
        
        # Fallback to tail
        reader.seek_tail()
        try:
            last = reader.get_previous()
            if last:
                self.cursor = last.get('__CURSOR')
        except:
            pass

    def start(self):
        self.cursor_dir.mkdir(parents=True, exist_ok=True)
        self.cursor = self._load_cursor()
        self.journal = systemd.journal.Reader()
        
        # Reuse same reader for determining scan range
        scan_start, scan_end = self._get_scan_range(self.journal, self.time_period)
        
        # Position main journal for new logs
        self._initialize_journal_position(self.journal)
        
        # Launch background scanner if range is valid
        if scan_start and scan_end and scan_start < scan_end:
            t = threading.Thread(target=self._scan_history_background, args=(scan_start, scan_end))
            t.daemon = True
            t.start()
        else:
            self.history_done = True

    def poll(self):
        events = []
        
        # Drain history queue (limit batch size)
        HISTORY_BATCH_SIZE = 100
        count = 0
        while not self.history_queue.empty() and count < HISTORY_BATCH_SIZE:
            try:
                events.append(self.history_queue.get_nowait())
                count += 1
            except queue.Empty:
                break
        
        # Check for new logs
        if not self.journal:
            return events

        for entry in self.journal:
            ev_dict = _entry_to_dict(entry)
            if ev_dict:
                events.append(LogEvent(**ev_dict))
                self.cursor = entry.get('__CURSOR')

        return events

    def stop(self):
        if self.cursor:
            try:
                with open(self.cursor_path, 'w') as f:
                    f.write(self.cursor)
            except Exception as e:
                print(f"Failed to save cursor: {e}")
        
        if self.journal:
            self.journal.close()
            self.journal = None
        
        print("Systemd source stopped.")