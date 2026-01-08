# Goal:
A friendly, purely local diagnostic agent that bridges the "App Gap" and "Tinker Tax" for non-technical users. It explains Linux errors in plain English and offers "One-Click" fixes.

## 1. High-Level Architecture
The app is designed to feel native to modern Linux (GNOME/Cinnamon/Plasma) while remaining extremely lightweight for older hardware.

- **Frontend**: Python 3.12+ with PyGObject (GTK4 & Libadwaita). This provides the "warm," modern UI with rounded corners, responsive layouts, and native Dark Mode support.
- **Log Ingestion**: python-systemd or pystemd. This talks directly to the systemd journal via C-bindings, avoiding the overhead of spawning terminal processes just to read logs.
- **The Brain (TinyLM)**: A 0.1B - 0.2B parameter model (e.g., a fine-tuned ModernBERT-Base or MiniMind) running on ONNX Runtime. Great for local inference and battery life.
  - **RAM**: ~200MB (using INT8 quantization).
  - **Inference**: Instant CPU-bound processing(no GPU required).
- **Permissions**: A custom Polkit (PolicyKit) rule allows Neighbor to read system logs.
- **Function**: Maps raw system errors (e.g., `iwlwifi 0000:00:14.3: Microcode SW error`) to a human-readable solution.

## 2. Core Functional Modules

| Module | Technical Implementation | Purpose |
|--- |--------------------------|---------|
| **The Ear (Log Watcher)** | sd-journal (systemd) | Real-time monitoring of hardware events (USB plugs, Wi-Fi drops, Bluetooth timeouts). |
| **The Translator (Semantic Parser)** | ONNX Runtime + TinyLM | Takes ERROR: [nvidia-drm] ... and outputs "Your graphics card is tired." |
| **The Workshop (Action Engine)** | VTE (Virtual Terminal Emulator) | An embedded terminal widget inside the app where suggested fixes are staged and run. |
| **Neighborly UI** | Libadwaita "StatusPage" | A "Health Dashboard" using friendly icons and warm colors instead of dense lists. |
| **Offline Brain** | SQLite | A local cache of known "safe" commands for common hardware fixes. |

## 3. "Neighborly" UX Flow

**1. Warm Notification:** Instead of "System Error," the user sees: "Hey, it looks like your controller isn't connecting. Want me to take a look?"
**2. Visual Diagnosis:** User opens Neighbor. They see a Health Ring (Green/Yellow/Red).
**3. Human Explanation:** The AI displays: "I see you're using an Xbox controller over Bluetooth. Sometimes the 'ERTM' setting interferes. I can toggle that for you."
**4. The Staged Fix:** A button [Fix it, Neighbor!] appears. Clicking it reveals the Glass Terminal where the command sudo xpadneo-fix is pre-typed.
**5. Closing the Loop:** The user hits Enter. Neighbor watches the log and confirms: "All set! Enjoy your game."

## 4. Deployment Strategy
To solve the "Python dependency" issue and make installation foolproof:

- **Flatpak (Primary):** Bundles the Python interpreter, the TinyLM weights, and all GTK/ONNX libraries into a single file. Users can install it with one click from GNOME Software or Flathub.
- **AppStream Metadata:** Provides the "Store Page" experience — high-res screenshots, user reviews, and clear descriptions of what Neighbor does.
- **Systemd Integration:** A small background service (the "Sentinel") that stays asleep until a critical system error is logged, ensuring zero battery drain.
