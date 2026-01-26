"""
This module provides a unified interface to access data from various sources.
No storage or classification logic is implemented here, just served to the main app.
"""

class Sources:
    def __init__(self, sources):
        # Initialize whatever the user wants to monitor
        self.sources = []
        
        if "audio" in sources:
            from .sources.audio.audio_source import AudioSource
            self.audio = AudioSource()
            self.sources.append(self.audio)
        if "kernel" in sources:
            from .sources.kernel.kernel_source import KernelSource
            self.kernel = KernelSource()
            self.sources.append(self.kernel)
        if "network" in sources:
            from .sources.network.network_source import NetworkSource
            self.network = NetworkSource()
            self.sources.append(self.network)
        if "sandbox" in sources:
            from .sources.sandbox.sandbox_source import SandboxSource
            self.sandbox = SandboxSource()
            self.sources.append(self.sandbox)
        if "systemd" in sources:
            from .sources.systemd.systemd_source import SystemdSource, TimePeriod
            self.systemd = SystemdSource(core_allocation = 8, time_period=TimePeriod.NOW)
            self.sources.append(self.systemd)
    
    def start(self):
        for source in self.sources:
            source.start()
    
    def stop(self):
        for source in self.sources:
            source.stop()
    
    def poll(self):
        events = []
        for source in self.sources:
            events.extend(source.poll())
        return events