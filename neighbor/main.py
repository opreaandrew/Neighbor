#!/usr/bin/env python3

from core.log_watcher import Watcher

"""Main program entry point."""

if __name__ == "__main__":
    watcher = Watcher()
    watcher.run()