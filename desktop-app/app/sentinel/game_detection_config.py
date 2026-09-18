# desktop-app/app/sentinel/game_detection_config.py

"""
Centralized configuration for the Universal Game Detection Protocol.

All process exclusion lists are maintained here as the single source of truth.
To exclude a new process from game detection, add it to the appropriate set below.
Do NOT hardcode exclusions in detection logic or other modules — import from here.
"""

# ── Critical OS / Driver Processes ────────────────────────────────────
# These must never be classified as games, terminated, or deprioritized.
SYSTEM_PROCESSES = frozenset({
    "system", "system idle process", "registry", "smss.exe",
    "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
    "svchost.exe", "fontdrvhost.exe", "dwm.exe", "explorer.exe",
    "taskhostw.exe", "winlogon.exe", "sihost.exe", "conhost.exe",
    "spoolsv.exe", "searchindexer.exe", "wudfhost.exe",
    "nvdisplay.container.exe", "securityhealthservice.exe", "ctfmon.exe",
    "memory compression", "dashost.exe", "dllhost.exe",
    "rundll32.exe", "runtimebroker.exe", "searchapp.exe",
    "startmenuexperiencehost.exe", "applicationframehost.exe",
    "audiodg.exe", "shellexperiencehost.exe", "searchhost.exe",
    # Anti-cheat services & security daemons (Strictly Untouched)
    "vgc.exe", "vgtray.exe", "riotclientservices.exe",
    "easyanticheat.exe", "easyanticheat_eos.exe",
    "beservice.exe", "battleye.exe",
})

# ── Non-Game Applications ─────────────────────────────────────────────
# Browsers, IDEs, launchers, chat apps, media players, updaters, shell UIs,
# and this application's own process. These pass Tier 1 exclusion immediately.
NON_GAME_BLACKLIST = frozenset({
    # Browsers
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
    "opera.exe", "vivaldi.exe", "iexplore.exe",
    # Development tools / IDEs
    "code.exe", "devenv.exe", "sublime_text.exe", "notepad.exe",
    "notepad++.exe", "pycharm64.exe", "idea64.exe", "rider64.exe",
    # Shell / system UI
    "taskmgr.exe", "cmd.exe", "powershell.exe", "pwsh.exe",
    "lockapp.exe", "calculator.exe",
    # Communication / chat
    "discord.exe", "slack.exe", "teams.exe", "zoom.exe",
    "webex.exe", "skype.exe", "telegram.exe",
    # Media / streaming
    "spotify.exe", "vlc.exe", "wmplayer.exe",
    # Cloud sync / updaters
    "onedrive.exe", "dropbox.exe", "googledrivesync.exe",
    "microsoftedgeupdate.exe", "googlechromeservice.exe",
    "updateassistant.exe", "jusched.exe",
    # Game launchers (not games themselves)
    "epicgameslauncher.exe", "steamwebhelper.exe",
    "gog.exe", "gogclient.exe",
    # System utilities
    "ccleaner64.exe", "ccleaner.exe",
    "adobeipcbroker.exe", "creative cloud.exe",
    "phoneexperiencehost.exe", "yourphone.exe",
    "searchprotocolhost.exe",
    "gamingservices.exe", "gamingservicesnet.exe",
    # This application
    "python.exe", "pythonw.exe", "fps_optimizer.exe",
})

# ── Bloatware Processes ───────────────────────────────────────────────
# Subset of non-game apps that can be safely deprioritized during gaming.
# Used by the background suppression logic, NOT by game detection.
BLOATWARE_PROCESSES = frozenset({
    "chrome.exe", "msedge.exe", "brave.exe", "firefox.exe",
    "onedrive.exe", "epicgameslauncher.exe", "ccleaner64.exe",
    "ccleaner.exe", "adobeipcbroker.exe", "creative cloud.exe",
    "phoneexperiencehost.exe", "yourphone.exe", "skype.exe",
    "teams.exe", "zoom.exe", "webex.exe", "slack.exe", "spotify.exe",
    "updateassistant.exe", "searchprotocolhost.exe",
    "microsoftedgeupdate.exe", "googlechromeservice.exe",
    "gamingservices.exe", "gamingservicesnet.exe",
    "dropbox.exe", "googledrivesync.exe", "jusched.exe",
})

# ── Tuning Constants ──────────────────────────────────────────────────
# Polling interval for idle game detection (seconds)
DEFAULT_POLL_INTERVAL_SEC = 1.5

# How many seconds of recent PresentMon frame data counts as "active"
FRAME_ACTIVITY_WINDOW_SEC = 3.0

# Minimum FPS threshold to consider a process as actively rendering
MIN_FRAME_ACTIVITY_FPS = 5.0
