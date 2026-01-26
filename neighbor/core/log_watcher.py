import os
import time
from data.sources_interface import Sources

"""
This module is the main entry point for the log watcher.
It initializes the log sources and starts monitoring the selected sources.
"""

class Watcher:
    def __init__(self):
        self.cpu_count = os.cpu_count() or 1
        self.running = True

    def run(self):
        print(f"Starting log watcher on {self.cpu_count} cores...")

        sources = ["systemd"]
        data = Sources(sources)
        
        try:
            data.start()
            
            while self.running:
                events = data.poll()
                if events:
                    print(f"Received {len(events)} new events.")
                    # Simple print of last few events for demo
                    for ev in events[-5:]:
                        print(f"[{ev.severity.name}] {ev.timestamp}: {ev.raw_message[:100]}")
                
                time.sleep(0.5) # Polling interval
                
        except Exception as e:
            print(f"Error: {e}")
        finally:
            data.stop()

if __name__ == "__main__":
    watcher = Watcher()
    watcher.run()
