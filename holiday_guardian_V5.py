"""
Holiday Guardian
v5 - 5-min break after each session, "Other" option in categories
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import datetime
import csv
import os
import json
import winsound
import pystray
from PIL import Image, ImageDraw


# ─────────────────────────────────────────────
# 1. Holiday Data
# ─────────────────────────────────────────────

BUILTIN_HOLIDAYS = {
    "2025-01-01","2025-01-28","2025-01-29","2025-01-30","2025-01-31",
    "2025-02-01","2025-02-02","2025-02-03","2025-02-04",
    "2025-04-04","2025-04-05","2025-04-06",
    "2025-05-01","2025-05-02","2025-05-03","2025-05-04","2025-05-05",
    "2025-05-31","2025-06-01","2025-06-02",
    "2025-10-01","2025-10-02","2025-10-03","2025-10-04",
    "2025-10-05","2025-10-06","2025-10-07","2025-10-08",
    "2026-01-01","2026-01-02","2026-01-03",
    "2026-02-17","2026-02-18","2026-02-19","2026-02-20",
    "2026-02-21","2026-02-22","2026-02-23","2026-02-24",
    "2026-04-04","2026-04-05","2026-04-06",
    "2026-05-01","2026-05-02","2026-05-03","2026-05-04","2026-05-05",
    "2026-06-19","2026-06-20","2026-06-21",
    "2026-10-01","2026-10-02","2026-10-03","2026-10-04",
    "2026-10-05","2026-10-06","2026-10-07","2026-10-08",
}

WORKDAYS_ON_WEEKEND = {
    "2025-01-26","2025-02-08","2025-04-27","2025-09-28","2025-10-11",
    "2026-02-15","2026-02-28","2026-10-10",
}

def fetch_holiday_data():
    try:
        import urllib.request
        holidays = set(BUILTIN_HOLIDAYS)
        for year in ["2025", "2026"]:
            url = f"https://timor.tech/api/holiday/year/{year}/"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                for date_str, info in data.get("holiday", {}).items():
                    if info.get("holiday"):
                        holidays.add(f"{year}-{date_str}")
        return holidays
    except Exception:
        return BUILTIN_HOLIDAYS

def is_holiday(date=None):
    if date is None:
        date = (datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(hours=8)).date()
    date_str = date.strftime("%Y-%m-%d")
    if date_str in WORKDAYS_ON_WEEKEND:
        return False
    if date_str in HOLIDAYS:
        return True
    if date.weekday() >= 5:
        return True
    return False


# ─────────────────────────────────────────────
# 2. Activity Categories
# ─────────────────────────────────────────────

ACTIVITY_CATEGORIES = {
    "Active Focus": [
        "Reading", "Writing", "Thinking",
        "Meditation", "Studying", "Coding", "Other"
    ],
    "Passive Focus": [
        "Movie", "Gaming", "Music",
        "Browsing Videos", "Social Media", "Other"
    ],
    "Mixed / Light": [
        "Walking", "Exercise", "Laundry",
        "Cooking", "Resting", "Housework", "Other"
    ],
}


# ─────────────────────────────────────────────
# 3. Record Module
# ─────────────────────────────────────────────

RECORDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "records")

def ensure_records_dir():
    os.makedirs(RECORDS_DIR, exist_ok=True)

def save_record(start_time, end_time, category, activity, note):
    ensure_records_dir()
    today = datetime.date.today().strftime("%Y-%m-%d")
    filepath = os.path.join(RECORDS_DIR, f"{today}.csv")
    file_exists = os.path.exists(filepath)
    with open(filepath, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Start", "End", "Category", "Activity", "Note"])
        writer.writerow([start_time, end_time, category, activity, note])


# ─────────────────────────────────────────────
# 4. Sound
# ─────────────────────────────────────────────

def beep(style="remind"):
    try:
        sounds = {
            "remind": winsound.MB_ICONEXCLAMATION,
            "start":  winsound.MB_ICONASTERISK,
            "done":   winsound.MB_OK,
            "break":  winsound.MB_ICONQUESTION,
        }
        winsound.MessageBeep(sounds.get(style, winsound.MB_OK))
    except Exception:
        pass


# ─────────────────────────────────────────────
# 5. Tray Icon
# ─────────────────────────────────────────────

def make_tray_icon(color="#27ae60"):
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size-2, size-2], fill=color)
    draw.ellipse([18, 18, size-18, size-18], fill="white")
    draw.ellipse([26, 26, size-26, size-26], fill=color)
    return img


# ─────────────────────────────────────────────
# 6. Reminder Popup (end of 30-min session)
# ─────────────────────────────────────────────

class ReminderPopup:
    def __init__(self, session_start, on_submit, on_snooze, snooze_count):
        self.on_submit = on_submit
        self.on_snooze = on_snooze
        self.snooze_count = snooze_count
        self.MAX_SNOOZE = 2

        self.win = tk.Toplevel()
        self.win.title("Holiday Guardian — Time to Move!")
        self.win.geometry("540x600")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.wm_attributes("-toolwindow", True)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close_attempt)
        self._build(session_start)
        self.win.grab_set()
        self.win.focus_force()

    def _build(self, session_start):
        BG = "#f5f5f5"
        ACCENT = "#2c3e50"
        self.win.configure(bg=BG)

        header = tk.Frame(self.win, bg="#2c3e50", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🧘  Time to Stand Up and Move!",
                 font=("Segoe UI", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(expand=True)

        tk.Label(self.win, text=f"Session started at:  {session_start}",
                 font=("Segoe UI", 9), bg=BG, fg="#777").pack(pady=(10, 0))

        ttk.Separator(self.win).pack(fill="x", padx=24, pady=10)

        tk.Label(self.win, text="What were you doing?",
                 font=("Segoe UI", 11, "bold"), bg=BG, fg=ACCENT).pack(anchor="w", padx=28)

        self.cat_var = tk.StringVar()
        self.act_var = tk.StringVar()

        cat_frame = tk.Frame(self.win, bg=BG)
        cat_frame.pack(fill="x", padx=28, pady=(6, 0))

        colors = ["#3498db", "#e74c3c", "#27ae60"]
        for i, cat in enumerate(ACTIVITY_CATEGORIES):
            tk.Radiobutton(cat_frame, text=f"  {cat}",
                           variable=self.cat_var, value=cat,
                           command=self._refresh_activities,
                           font=("Segoe UI", 10),
                           fg=colors[i], bg=BG,
                           activebackground=BG,
                           selectcolor=BG).pack(anchor="w", pady=1)

        tk.Label(self.win, text="Specific activity:",
                 font=("Segoe UI", 11, "bold"), bg=BG, fg=ACCENT).pack(anchor="w", padx=28, pady=(12, 0))

        self.combo = ttk.Combobox(self.win, textvariable=self.act_var,
                                   state="readonly", width=38,
                                   font=("Segoe UI", 10))
        self.combo.pack(padx=28, anchor="w", pady=(4, 0))

        # "Other" note — shown only when Other is selected
        self.other_label = tk.Label(self.win, text="Describe your activity:",
                                     font=("Segoe UI", 10, "bold"), bg=BG, fg=ACCENT)
        self.other_entry = tk.Entry(self.win, font=("Segoe UI", 10),
                                     relief="solid", bd=1, width=40)
        self.combo.bind("<<ComboboxSelected>>", self._on_activity_change)

        tk.Label(self.win, text="Note  (optional):",
                 font=("Segoe UI", 11, "bold"), bg=BG, fg=ACCENT).pack(anchor="w", padx=28, pady=(14, 0))
        self.note = tk.Text(self.win, height=3, font=("Segoe UI", 9),
                             relief="solid", bd=1, wrap="word")
        self.note.pack(padx=28, fill="x", pady=(4, 0))

        ttk.Separator(self.win).pack(fill="x", padx=24, pady=14)

        bf = tk.Frame(self.win, bg=BG)
        bf.pack(pady=(0, 18))

        tk.Button(bf, text="✅  Submit & Start Break",
                  font=("Segoe UI", 11, "bold"),
                  bg="#27ae60", fg="white", relief="flat",
                  padx=20, pady=10, cursor="hand2",
                  command=self._submit).pack(side="left", padx=10)

        if self.snooze_count < self.MAX_SNOOZE:
            left = self.MAX_SNOOZE - self.snooze_count
            tk.Button(bf, text=f"⏰  Snooze 15 min  ({left} left)",
                      font=("Segoe UI", 10),
                      bg="#e67e22", fg="white", relief="flat",
                      padx=16, pady=10, cursor="hand2",
                      command=self._snooze).pack(side="left", padx=10)

    def _refresh_activities(self):
        items = ACTIVITY_CATEGORIES.get(self.cat_var.get(), [])
        self.combo["values"] = items
        if items:
            self.combo.current(0)
        self._on_activity_change()

    def _on_activity_change(self, event=None):
        if self.act_var.get() == "Other":
            self.other_label.pack(anchor="w", padx=28, pady=(6, 0))
            self.other_entry.pack(padx=28, anchor="w", pady=(2, 0))
        else:
            self.other_label.pack_forget()
            self.other_entry.pack_forget()

    def _submit(self):
        if not self.cat_var.get():
            messagebox.showwarning("Missing Category",
                                   "Please select a category first.", parent=self.win)
            return
        activity = self.act_var.get()
        if activity == "Other":
            custom = self.other_entry.get().strip()
            activity = f"Other: {custom}" if custom else "Other"
        note = self.note.get("1.0", "end").strip()
        self.win.destroy()
        self.on_submit(self.cat_var.get(), activity, note)

    def _snooze(self):
        self.win.destroy()
        self.on_snooze()

    def _on_close_attempt(self):
        messagebox.showinfo("Please Submit First",
                            "Fill in your activity record before closing.",
                            parent=self.win)


# ─────────────────────────────────────────────
# 7. Break Popup (5-min break notification)
# ─────────────────────────────────────────────

class BreakPopup:
    def __init__(self, on_confirm):
        self.on_confirm = on_confirm

        self.win = tk.Toplevel()
        self.win.title("Holiday Guardian — Break Time!")
        self.win.geometry("420x260")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.wm_attributes("-toolwindow", True)
        self.win.protocol("WM_DELETE_WINDOW", lambda: None)  # block close
        self._build()
        self.win.grab_set()
        self.win.focus_force()

    def _build(self):
        BG = "#f0f4f8"
        self.win.configure(bg=BG)

        header = tk.Frame(self.win, bg="#3498db", height=55)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="☕  Break Time is Over!",
                 font=("Segoe UI", 13, "bold"),
                 bg="#3498db", fg="white").pack(expand=True)

        tk.Label(self.win,
                 text="Your 5-minute break has ended.\nReady to start the next 30-minute session?",
                 font=("Segoe UI", 11), bg=BG, fg="#2c3e50",
                 justify="center").pack(pady=28)

        tk.Button(self.win, text="✅  Yes, Start New Session",
                  font=("Segoe UI", 12, "bold"),
                  bg="#27ae60", fg="white", relief="flat",
                  padx=24, pady=12, cursor="hand2",
                  command=self._confirm).pack()

    def _confirm(self):
        self.win.destroy()
        self.on_confirm()


# ─────────────────────────────────────────────
# 8. Status Popup
# ─────────────────────────────────────────────

class StatusPopup:
    def __init__(self, running, on_break, next_time, session_start):
        self.win = tk.Toplevel()
        self.win.title("Holiday Guardian — Status")
        self.win.geometry("400x280")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.wm_attributes("-toolwindow", True)
        self.win.focus_force()
        self._build(running, on_break, next_time, session_start)

    def _build(self, running, on_break, next_time, session_start):
        BG = "#f0f4f8"
        self.win.configure(bg=BG)

        if on_break:
            hdr_color, hdr_text = "#3498db", "🛡️  Holiday Guardian  —  On Break"
        elif running:
            hdr_color, hdr_text = "#27ae60", "🛡️  Holiday Guardian  —  Running"
        else:
            hdr_color, hdr_text = "#e74c3c", "🛡️  Holiday Guardian  —  Stopped"

        header = tk.Frame(self.win, bg=hdr_color, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=hdr_text,
                 font=("Segoe UI", 12, "bold"),
                 bg=hdr_color, fg="white").pack(expand=True)

        content = tk.Frame(self.win, bg=BG)
        content.pack(fill="both", expand=True, padx=30, pady=20)

        if running or on_break:
            phase = "Break" if on_break else "Session"
            self._row(content, "Current phase:", phase, BG)
            self._row(content, "Started at:", session_start, BG)

            if next_time:
                now = datetime.datetime.now()
                diff = next_time - now
                total_secs = max(0, int(diff.total_seconds()))
                mins = total_secs // 60
                secs = total_secs % 60
                countdown = f"{mins} min  {secs} sec"
                next_str = next_time.strftime("%H:%M")
            else:
                countdown = "Preparing..."
                next_str = "—"

            label = "Break ends at:" if on_break else "Next reminder at:"
            self._row(content, label, next_str, BG)

            tk.Label(content, text=countdown,
                     font=("Segoe UI", 22, "bold"),
                     bg=BG, fg="#e67e22").pack(pady=(10, 0))
            sublabel = "until break ends" if on_break else "until next break"
            tk.Label(content, text=sublabel,
                     font=("Segoe UI", 9), bg=BG, fg="#999").pack()
        else:
            tk.Label(content,
                     text="Guardian is not running.\nRight-click the tray icon and select Start.",
                     font=("Segoe UI", 10), bg=BG, fg="#888",
                     justify="center").pack(pady=20)

        ttk.Separator(self.win).pack(fill="x", padx=20)
        tk.Button(self.win, text="Close", command=self.win.destroy,
                  font=("Segoe UI", 9), relief="flat",
                  bg="#dde3ea", padx=20, pady=5,
                  cursor="hand2").pack(pady=12)

    def _row(self, parent, label, value, bg):
        f = tk.Frame(parent, bg=bg)
        f.pack(fill="x", pady=2)
        tk.Label(f, text=label, font=("Segoe UI", 9),
                 bg=bg, fg="#888", width=18, anchor="w").pack(side="left")
        tk.Label(f, text=value, font=("Segoe UI", 10, "bold"),
                 bg=bg, fg="#2c3e50").pack(side="left")


# ─────────────────────────────────────────────
# 9. Main Controller
# ─────────────────────────────────────────────

class HolidayGuardian:
    INTERVAL    = 30   # minutes per session
    BREAK_TIME  = 5    # minutes for break
    SNOOZE_TIME = 15   # minutes per snooze

    def __init__(self):
        self.running      = False
        self.on_break     = False
        self.snooze_count = 0
        self.session_start = ""
        self.timer         = None
        self.next_event_time = None

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.wm_attributes("-toolwindow", True)
        self._setup_tray()

    def _setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("View Status",  self._tray_status, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start",        self._tray_start),
            pystray.MenuItem("Stop",         self._tray_stop),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Records", self._tray_records),
            pystray.MenuItem("Quit",         self._tray_quit),
        )
        self.tray = pystray.Icon(
            "hg", make_tray_icon("#e74c3c"), "Holiday Guardian (Stopped)", menu
        )

    def _tray_status(self, *_):
        self.root.after(0, self._show_status)

    def _tray_start(self, *_):
        self.root.after(0, self._start)

    def _tray_stop(self, *_):
        self.root.after(0, self._stop)

    def _tray_records(self, *_):
        ensure_records_dir()
        os.startfile(RECORDS_DIR)

    def _tray_quit(self, *_):
        self._stop()
        self.tray.stop()
        self.root.after(0, self.root.destroy)

    def _show_status(self):
        StatusPopup(
            running=self.running,
            on_break=self.on_break,
            next_time=self.next_event_time,
            session_start=self.session_start,
        )

    def _set_tray(self, running, on_break=False):
        if on_break:
            color, title = "#3498db", "Holiday Guardian — On Break ☕"
        elif running:
            color, title = "#27ae60", "Holiday Guardian — Running ✅"
        else:
            color, title = "#e74c3c", "Holiday Guardian — Stopped"
        self.tray.icon = make_tray_icon(color)
        self.tray.title = title

    def _start(self):
        if self.running:
            self._show_status()
            return
        if not is_holiday():
            if not messagebox.askyesno("Not a Holiday",
                                        "Today is a workday. Start anyway?"):
                return
        self.running = True
        self.on_break = False
        self.snooze_count = 0
        self.session_start = datetime.datetime.now().strftime("%H:%M")
        self._set_tray(True)
        beep("start")
        self._schedule_session()

    def _stop(self):
        self.running = False
        self.on_break = False
        self.next_event_time = None
        if self.timer:
            self.timer.cancel()
        self._set_tray(False)

    def _schedule_session(self):
        if not self.running:
            return
        self.on_break = False
        self.next_event_time = (datetime.datetime.now()
                                + datetime.timedelta(minutes=self.INTERVAL))
        self.timer = threading.Timer(self.INTERVAL * 60, self._fire_reminder)
        self.timer.daemon = True
        self.timer.start()
        self._set_tray(True, on_break=False)

    def _schedule_break(self):
        if not self.running:
            return
        self.on_break = True
        self.next_event_time = (datetime.datetime.now()
                                + datetime.timedelta(minutes=self.BREAK_TIME))
        self.timer = threading.Timer(self.BREAK_TIME * 60, self._fire_break_end)
        self.timer.daemon = True
        self.timer.start()
        self._set_tray(True, on_break=True)

    def _fire_reminder(self):
        if not self.running:
            return
        beep("remind")
        end = datetime.datetime.now().strftime("%H:%M")
        self.root.after(0, lambda: self._show_reminder(end))

    def _fire_break_end(self):
        if not self.running:
            return
        beep("break")
        self.root.after(0, self._show_break_end)

    def _show_reminder(self, end_time):
        ReminderPopup(
            session_start=self.session_start,
            on_submit=lambda c, a, n: self._submitted(end_time, c, a, n),
            on_snooze=self._snoozed,
            snooze_count=self.snooze_count,
        )

    def _show_break_end(self):
        BreakPopup(on_confirm=self._break_confirmed)

    def _submitted(self, end_time, cat, act, note):
        save_record(self.session_start, end_time, cat, act, note)
        self.snooze_count = 0
        beep("done")
        # Start 5-min break
        self.session_start = datetime.datetime.now().strftime("%H:%M")
        messagebox.showinfo("Break Time!",
                            f"Record saved! Take a 5-minute break now.\n"
                            f"A reminder will pop up when break is over.\n\n"
                            f"Saved to:\n{RECORDS_DIR}")
        self._schedule_break()

    def _break_confirmed(self):
        # User confirmed break is over — start new session
        self.session_start = datetime.datetime.now().strftime("%H:%M")
        beep("start")
        self._schedule_session()

    def _snoozed(self):
        self.snooze_count += 1
        self.next_event_time = (datetime.datetime.now()
                                + datetime.timedelta(minutes=self.SNOOZE_TIME))
        self.timer = threading.Timer(self.SNOOZE_TIME * 60, self._fire_reminder)
        self.timer.daemon = True
        self.timer.start()

    def run(self):
        threading.Thread(target=self.tray.run, daemon=True).start()
        self.root.mainloop()


# ─────────────────────────────────────────────
# 10. Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("Loading holiday data...")
    HOLIDAYS = fetch_holiday_data()
    print(f"Loaded {len(HOLIDAYS)} holiday days (2025-2026).")
    app = HolidayGuardian()
    app.run()
