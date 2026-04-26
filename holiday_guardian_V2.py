"""
Holiday Guardian / 假日守护者
v2 - 系统托盘版本（无任务栏图标）
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
# 1. 假期数据
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
    "2026-04-05","2026-04-06",
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
        url = "https://timor.tech/api/holiday/year/2025/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            holidays = set()
            for date_str, info in data.get("holiday", {}).items():
                if info.get("holiday"):
                    holidays.add(f"2025-{date_str}")
            return holidays if holidays else BUILTIN_HOLIDAYS
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
# 2. 活动分类
# ─────────────────────────────────────────────

ACTIVITY_CATEGORIES = {
    "主动注意力 Active Focus": [
        "读书 Reading","写作 Writing","思考 Thinking",
        "冥想 Meditation","学习 Studying","编程 Coding"
    ],
    "被动注意力 Passive Focus": [
        "电影 Movie","游戏 Gaming","音乐 Music",
        "刷视频 Browsing Videos","社交媒体 Social Media"
    ],
    "中间态 Mixed": [
        "走路 Walking","运动 Exercise","洗衣服 Laundry",
        "做饭 Cooking","休息 Resting","家务 Housework"
    ],
}


# ─────────────────────────────────────────────
# 3. 记录模块
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
            writer.writerow(["开始时间","结束时间","分类","活动","备注"])
        writer.writerow([start_time, end_time, category, activity, note])


# ─────────────────────────────────────────────
# 4. 提示音
# ─────────────────────────────────────────────

def beep(style="remind"):
    try:
        sounds = {
            "remind": winsound.MB_ICONEXCLAMATION,
            "start":  winsound.MB_ICONASTERISK,
            "done":   winsound.MB_OK,
        }
        winsound.MessageBeep(sounds.get(style, winsound.MB_OK))
    except Exception:
        pass


# ─────────────────────────────────────────────
# 5. 托盘图标生成
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
# 6. 弹窗
# ─────────────────────────────────────────────

class ReminderPopup:
    def __init__(self, session_start, on_submit, on_snooze, snooze_count):
        self.on_submit = on_submit
        self.on_snooze = on_snooze
        self.snooze_count = snooze_count
        self.MAX_SNOOZE = 2

        self.win = tk.Toplevel()
        self.win.title("假日守护者 Holiday Guardian")
        self.win.geometry("520x570")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.wm_attributes("-toolwindow", True)   # 不在任务栏显示
        self.win.protocol("WM_DELETE_WINDOW", self._on_close_attempt)
        self._build(session_start)
        self.win.grab_set()
        self.win.focus_force()

    def _build(self, session_start):
        BG = "#f5f5f5"
        self.win.configure(bg=BG)

        tk.Label(self.win, text="🧘 起身活动时间到！Time to Move!",
                 font=("Microsoft YaHei", 14, "bold"), bg=BG, fg="#333").pack(pady=(18,4))
        tk.Label(self.win, text=f"本阶段开始 Started: {session_start}",
                 font=("Microsoft YaHei", 9), bg=BG, fg="#666").pack()

        ttk.Separator(self.win).pack(fill="x", padx=20, pady=12)

        tk.Label(self.win, text="刚才在做什么？What were you doing?",
                 font=("Microsoft YaHei", 10, "bold"), bg=BG).pack(anchor="w", padx=24)

        self.cat_var = tk.StringVar()
        self.act_var = tk.StringVar()

        for cat in ACTIVITY_CATEGORIES:
            tk.Radiobutton(self.win, text=cat, variable=self.cat_var, value=cat,
                           command=self._refresh_activities,
                           font=("Microsoft YaHei", 9), bg=BG,
                           activebackground=BG).pack(anchor="w", padx=36)

        tk.Label(self.win, text="具体活动 Activity:",
                 font=("Microsoft YaHei", 10, "bold"), bg=BG).pack(anchor="w", padx=24, pady=(10,0))
        self.combo = ttk.Combobox(self.win, textvariable=self.act_var,
                                   state="readonly", width=36,
                                   font=("Microsoft YaHei", 10))
        self.combo.pack(padx=24, anchor="w", pady=(4,0))

        tk.Label(self.win, text="备注 Note (可选):",
                 font=("Microsoft YaHei", 10, "bold"), bg=BG).pack(anchor="w", padx=24, pady=(12,0))
        self.note = tk.Text(self.win, height=3, width=53,
                             font=("Microsoft YaHei", 9), relief="solid", bd=1)
        self.note.pack(padx=24, pady=(4,0))

        ttk.Separator(self.win).pack(fill="x", padx=20, pady=14)

        bf = tk.Frame(self.win, bg=BG)
        bf.pack(pady=(0,16))

        tk.Button(bf, text="✅ 提交记录 Submit",
                  font=("Microsoft YaHei", 11, "bold"),
                  bg="#4CAF50", fg="white", relief="flat",
                  padx=16, pady=8, command=self._submit).pack(side="left", padx=8)

        if self.snooze_count < self.MAX_SNOOZE:
            left = self.MAX_SNOOZE - self.snooze_count
            tk.Button(bf, text=f"⏰ 再给我15分钟 Snooze ({left}次剩余)",
                      font=("Microsoft YaHei", 10),
                      bg="#FF9800", fg="white", relief="flat",
                      padx=12, pady=8, command=self._snooze).pack(side="left", padx=8)

    def _refresh_activities(self):
        items = ACTIVITY_CATEGORIES.get(self.cat_var.get(), [])
        self.combo["values"] = items
        if items:
            self.combo.current(0)

    def _submit(self):
        if not self.cat_var.get():
            messagebox.showwarning("提示", "请先选择分类\nPlease select a category", parent=self.win)
            return
        note = self.note.get("1.0", "end").strip()
        self.win.destroy()
        self.on_submit(self.cat_var.get(), self.act_var.get(), note)

    def _snooze(self):
        self.win.destroy()
        self.on_snooze()

    def _on_close_attempt(self):
        messagebox.showinfo("提示", "请先填写记录\nPlease submit first.", parent=self.win)


# ─────────────────────────────────────────────
# 7. 主控制器
# ─────────────────────────────────────────────

class HolidayGuardian:
    INTERVAL = 30
    SNOOZE   = 15

    def __init__(self):
        self.running = False
        self.snooze_count = 0
        self.session_start = ""
        self.timer = None

        # 隐藏的 tkinter 根窗口
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.wm_attributes("-toolwindow", True)

        self._setup_tray()

    def _setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("▶ 启动 Start",         self._tray_start, default=True),
            pystray.MenuItem("■ 停止 Stop",           self._tray_stop),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📂 打开记录 Records",   self._tray_records),
            pystray.MenuItem("❌ 退出 Quit",          self._tray_quit),
        )
        self.tray = pystray.Icon(
            "hg", make_tray_icon(), "假日守护者（已停止）", menu
        )

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

    def _set_tray_color(self, running):
        self.tray.icon = make_tray_icon("#27ae60" if running else "#e74c3c")
        self.tray.title = "假日守护者 | " + ("运行中 ✅" if running else "已停止")

    def _start(self):
        if self.running:
            return
        if not is_holiday():
            if not messagebox.askyesno("非假期", "今天是工作日，确定启动？\nWorkday detected. Start anyway?"):
                return
        self.running = True
        self.snooze_count = 0
        self.session_start = datetime.datetime.now().strftime("%H:%M")
        self._set_tray_color(True)
        beep("start")
        self._schedule(self.INTERVAL)

    def _stop(self):
        self.running = False
        if self.timer:
            self.timer.cancel()
        self._set_tray_color(False)

    def _schedule(self, minutes):
        if not self.running:
            return
        self.timer = threading.Timer(minutes * 60, self._fire)
        self.timer.daemon = True
        self.timer.start()

    def _fire(self):
        if not self.running:
            return
        beep("remind")
        end = datetime.datetime.now().strftime("%H:%M")
        self.root.after(0, lambda: self._popup(end))

    def _popup(self, end_time):
        ReminderPopup(
            session_start=self.session_start,
            on_submit=lambda c, a, n: self._submitted(end_time, c, a, n),
            on_snooze=self._snoozed,
            snooze_count=self.snooze_count,
        )

    def _submitted(self, end_time, cat, act, note):
        save_record(self.session_start, end_time, cat, act, note)
        self.snooze_count = 0
        self.session_start = datetime.datetime.now().strftime("%H:%M")
        beep("done")
        messagebox.showinfo("✅ 已保存 Saved",
                            f"记录已保存！新阶段开始。\nRecord saved! New session started.\n\n{RECORDS_DIR}")
        self._schedule(self.INTERVAL)

    def _snoozed(self):
        self.snooze_count += 1
        self._schedule(self.SNOOZE)

    def run(self):
        threading.Thread(target=self.tray.run, daemon=True).start()
        self.root.mainloop()


# ─────────────────────────────────────────────
# 8. 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("加载假期数据... Loading holidays...")
    HOLIDAYS = fetch_holiday_data()
    print(f"已加载 {len(HOLIDAYS)} 天假期数据")
    app = HolidayGuardian()
    app.run()
