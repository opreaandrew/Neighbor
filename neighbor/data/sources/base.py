#!/usr/bin/env python3
"""
Base classes and contracts for log sources.

All log sources must:
1. Inherit from LogSource
2. Return LogEvent instances
"""

from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum


class Severity(Enum):
    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5

@dataclass
class LogEvent:
    """
    A log event from any source.
    """
    source: str           # 'systemd', 'kernel', 'audio', 'network', 'packages'
    severity: Severity
    timestamp: int        # Unix timestamp in seconds
    subsystem: str        # e.g., 'NetworkManager.service', 'iwlwifi'
    raw_message: str      # MUST be sanitized - no IPs, usernames, emails
    structured_data: dict # Source-specific metadata


class LogSource(ABC):
    """
    Base class for log sources.
    """
    
    @abstractmethod
    def start(self):
        """    
        - open handles
        - validate permissions
        - load checkpoints (if any)
        - initialize cursors / offsets
        """
        pass

    @abstractmethod
    def poll(self) -> list[LogEvent]:
        """
        - Returns a list of log events since the last poll.
        - The list should be empty if no new logs are available.
        - All returned LogEvents MUST have sanitized raw_message.
        """
        pass

    @abstractmethod
    def stop(self):
        """
        - close file descriptors
        - flush buffers
        - persist cursor state (optional)
        """
        pass