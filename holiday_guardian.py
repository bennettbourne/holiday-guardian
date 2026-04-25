"""
Holiday Guardian / 假日守护者
帮助宅男在节假日合理使用电脑，定期起身活动。
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import datetime
import csv
import os
import json
import winsound  # Windows系统提示音
import sys

# ─────────────────────────────────────────────
# 1. 假期数据（2025-2026 中国法定节假日 + 周末）
#    联网失败时自动降级为内置数据
# ─────────────────────────────────────────────

BUILTIN_HOLIDAYS = {
    # 2025
    "2025-01-01", "2025-01-28", "2025-01-29", "2025-01-30",
    "2025-01-31", "2025-02-01", "2025-02-02", "2025-02-03",
    "2025-02-04", "2025-04-04", "2025-04-05", "2025-04-06",
    "2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04",
    "2025-05-05", "2025-05-31", "2025-06-01", "2025-06-02",
    "2025-10-01", "2025-10-02", "2025-10-03", "2025-10-04",
    "2025-10-05", "2025-10-06", "2025-10-07", "2025-10-08",
    # 2026
    "2026-01-01", "2026-01-02", "2026-01-03",
    "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",
    "2026-02-21", "2026-02-22", "2026-02-23", "2026-02-24",
    "2026-04-05", "2026-04-06",
    "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",
    "2026-06-19", "2026-06-20", "2026-06-21",
    "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04",
    "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08",
}

# 调班补班（这些日期虽然是周六日，但需要上班）
WORKDAYS_ON_WEEKEND = {
    "2025-01-26", "2025-02-08", "2025-04-27", "2025-09-28", "2025-10-11",
    "2026-02-15", "2026-02-28", "2026-10-10",
}

def fetch_holiday_data():
    """尝试联网获取最新假期数据，失败则使用内置数据"""
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
    """判断给定日期（默认今天北京时间）是否为非工作日"""
    if date is None:
        # 北京时间 UTC+8
        date = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        date = date.date()
    date_str = date.strftime("%Y-%m-%d")

    # 调班日：周末但要上班
    if date_str in WORKDAYS_ON_WEEKEND:
        return False
    # 法定假日
    if date_str in HOLIDAYS:
        return True
    # 周六日
    if date.weekday() >= 5:
        return True
    return False


# ─────────────────────────────────────────────
# 2. 活动分类数据
# ─────────────────────────────────────────────

ACTIVITY_CATEGORIES = {
    "主动注意力 Active Focus": ["读书 Reading", "写作 Writing", "思考 Thinking",
                                "冥想 Meditation", "学习 Studying", "编程 Coding"],
    "被动注意力 Passive Focus": ["电影 Movie", "游戏 Gaming", "音乐 Music",
                                  "刷视频 Browsing Videos", "社交媒体 Social Media"],
    "中间态 Mixed":             ["走路 Walking", "运动 Exercise", "洗衣服 Laundry",
                                  "做饭 Cooking", "休息 Resting", "家务 Housework"],
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
            writer.writerow(["开始时间 Start", "结束时间 End",
                             "分类 Category", "活动 Activity", "备注 Note"])
        writer.writerow([start_time, end_time, category, activity, note])


# ─────────────────────────────────────────────
# 4. 提示音
# ─────────────────────────────────────────────

def beep(style="remind"):
    """播放系统提示音"""
    try:
        if style == "remind":
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        elif style == "start":
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        elif style == "done":
            winsound.MessageBeep(winsound.MB_OK)
    except Exception:
        pass  # 非Windows环境静默失败


# ─────────────────────────────────────────────
# 5. 弹窗 UI
# ─────────────────────────────────────────────

class ReminderPopup:
    def __init__(self, session_start: str, on_submit, on_snooze, snooze_count: int):
        self.on_submit = on_submit
        self.on_snooze = on_snooze
        self.snooze_count = snooze_count  # 已延长次数
        self.max_snooze = 2

        self.root = tk.Toplevel()
        self.root.title("假日守护者 Holiday Guardian")
        self.root.geometry("520x560")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

        self._build_ui(session_start)
        self.root.grab_set()

    def _build_ui(self, session_start):
        root = self.root
        BG = "#f5f5f5"
        root.configure(bg=BG)

        # 标题
        tk.Label(root, text="🧘 起身活动时间到！Time to Move!",
                 font=("Microsoft YaHei", 14, "bold"),
                 bg=BG, fg="#333").pack(pady=(18, 4))

        tk.Label(root, text=f"本阶段开始 Session started: {session_start}",
                 font=("Microsoft YaHei", 9), bg=BG, fg="#666").pack()

        ttk.Separator(root, orient="horizontal").pack(fill="x", padx=20, pady=12)

        # 分类选择
        tk.Label(root, text="刚才在做什么？ What were you doing?",
                 font=("Microsoft YaHei", 10, "bold"), bg=BG).pack(anchor="w", padx=24)

        self.category_var = tk.StringVar()
        self.activity_var = tk.StringVar()

        cat_frame = tk.Frame(root, bg=BG)
        cat_frame.pack(fill="x", padx=24, pady=(6, 0))

        for cat in ACTIVITY_CATEGORIES:
            short = cat.split()[0]  # 只显示中文部分作为按钮
            rb = tk.Radiobutton(cat_frame, text=cat,
                                variable=self.category_var, value=cat,
                                command=self._update_activities,
                                font=("Microsoft YaHei", 9),
                                bg=BG, activebackground=BG)
            rb.pack(anchor="w")

        # 活动选择
        tk.Label(root, text="具体活动 Specific activity:",
                 font=("Microsoft YaHei", 10, "bold"), bg=BG).pack(anchor="w", padx=24, pady=(10,0))

        self.activity_combo = ttk.Combobox(root, textvariable=self.activity_var,
                                            state="readonly", width=35,
                                            font=("Microsoft YaHei", 10))
        self.activity_combo.pack(padx=24, pady=(4, 0), anchor="w")

        # 备注
        tk.Label(root, text="备注 Note (可选 optional):",
                 font=("Microsoft YaHei", 10, "bold"), bg=BG).pack(anchor="w", padx=24, pady=(12,0))

        self.note_text = tk.Text(root, height=3, width=52,
                                  font=("Microsoft YaHei", 9),
                                  relief="solid", bd=1)
        self.note_text.pack(padx=24, pady=(4, 0))

        ttk.Separator(root, orient="horizontal").pack(fill="x", padx=20, pady=14)

        # 按钮区
        btn_frame = tk.Frame(root, bg=BG)
        btn_frame.pack(pady=(0, 16))

        tk.Button(btn_frame, text="✅ 提交记录 Submit",
                  font=("Microsoft YaHei", 11, "bold"),
                  bg="#4CAF50", fg="white", relief="flat",
                  padx=16, pady=8,
                  command=self._submit).pack(side="left", padx=8)

        snooze_text = f"⏰ 再给我15分钟 Snooze ({self.max_snooze - self.snooze_count}次剩余)"
        self.snooze_btn = tk.Button(btn_frame, text=snooze_text,
                                     font=("Microsoft YaHei", 10),
                                     bg="#FF9800", fg="white", relief="flat",
                                     padx=12, pady=8,
                                     command=self._snooze)
        if self.snooze_count < self.max_snooze:
            self.snooze_btn.pack(side="left", padx=8)

    def _update_activities(self):
        cat = self.category_var.get()
        activities = ACTIVITY_CATEGORIES.get(cat, [])
        self.activity_combo["values"] = activities
        if activities:
            self.activity_combo.current(0)

    def _submit(self):
        cat = self.category_var.get()
        act = self.activity_var.get()
        if not cat:
            messagebox.showwarning("提示", "请选择活动分类\nPlease select a category", parent=self.root)
            return
        note = self.note_text.get("1.0", "end").strip()
        self.root.destroy()
        self.on_submit(cat, act, note)

    def _snooze(self):
        self.root.destroy()
        self.on_snooze()

    def _on_close_attempt(self):
        messagebox.showinfo("提示 Reminder",
                            "请先填写记录再关闭\nPlease submit your record first.",
                            parent=self.root)


# ─────────────────────────────────────────────
# 6. 主控制器
# ─────────────────────────────────────────────

class HolidayGuardian:
    INTERVAL_MINUTES = 30
    SNOOZE_MINUTES = 15
    MAX_SNOOZE = 2

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("假日守护者 Holiday Guardian")
        self.root.geometry("360x220")
        self.root.resizable(False, False)

        self.snooze_count = 0
        self.session_start = datetime.datetime.now().strftime("%H:%M")
        self.running = False
        self.timer_thread = None
        self._next_popup_time = None

        self._build_main_ui()

    def _build_main_ui(self):
        BG = "#f0f4f8"
        self.root.configure(bg=BG)

        tk.Label(self.root, text="🛡️ 假日守护者",
                 font=("Microsoft YaHei", 16, "bold"),
                 bg=BG, fg="#2c3e50").pack(pady=(20, 2))
        tk.Label(self.root, text="Holiday Guardian",
                 font=("Microsoft YaHei", 10),
                 bg=BG, fg="#7f8c8d").pack()

        self.status_label = tk.Label(self.root, text="状态：未启动 Status: Stopped",
                                      font=("Microsoft YaHei", 9),
                                      bg=BG, fg="#e74c3c")
        self.status_label.pack(pady=(14, 0))

        self.next_label = tk.Label(self.root, text="",
                                    font=("Microsoft YaHei", 9),
                                    bg=BG, fg="#27ae60")
        self.next_label.pack(pady=(4, 0))

        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(pady=18)

        self.start_btn = tk.Button(btn_frame, text="▶ 启动 Start",
                                    font=("Microsoft YaHei", 11, "bold"),
                                    bg="#27ae60", fg="white", relief="flat",
                                    padx=16, pady=8,
                                    command=self.start)
        self.start_btn.pack(side="left", padx=8)

        self.stop_btn = tk.Button(btn_frame, text="■ 停止 Stop",
                                   font=("Microsoft YaHei", 11),
                                   bg="#e74c3c", fg="white", relief="flat",
                                   padx=16, pady=8,
                                   command=self.stop,
                                   state="disabled")
        self.stop_btn.pack(side="left", padx=8)

        tk.Button(self.root, text="📂 打开记录文件夹 Open Records",
                  font=("Microsoft YaHei", 9),
                  bg="#ecf0f1", fg="#2c3e50", relief="flat",
                  command=self._open_records).pack()

    def start(self):
        if not is_holiday():
            if not messagebox.askyesno("今天不是假期 Not a Holiday",
                                        "今天是工作日，确定要启动守护者吗？\n"
                                        "Today is a workday. Start anyway?"):
                return

        self.running = True
        self.snooze_count = 0
        self.session_start = datetime.datetime.now().strftime("%H:%M")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="状态：运行中 Status: Running ✅", fg="#27ae60")
        beep("start")
        self._schedule_next(self.INTERVAL_MINUTES)

    def stop(self):
        self.running = False
        if self.timer_thread:
            self.timer_thread.cancel()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="状态：已停止 Status: Stopped", fg="#e74c3c")
        self.next_label.config(text="")

    def _schedule_next(self, minutes):
        if not self.running:
            return
        next_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        self.next_label.config(
            text=f"下次提醒 Next reminder: {next_time.strftime('%H:%M')}"
        )
        self.timer_thread = threading.Timer(minutes * 60, self._trigger_popup)
        self.timer_thread.daemon = True
        self.timer_thread.start()

    def _trigger_popup(self):
        if not self.running:
            return
        beep("remind")
        end_time = datetime.datetime.now().strftime("%H:%M")
        self.root.after(0, lambda: self._show_popup(end_time))

    def _show_popup(self, end_time):
        popup = ReminderPopup(
            session_start=self.session_start,
            on_submit=lambda cat, act, note: self._on_submit(end_time, cat, act, note),
            on_snooze=self._on_snooze,
            snooze_count=self.snooze_count,
        )

    def _on_submit(self, end_time, category, activity, note):
        save_record(self.session_start, end_time, category, activity, note)
        self.snooze_count = 0
        self.session_start = datetime.datetime.now().strftime("%H:%M")
        beep("done")
        messagebox.showinfo("✅ 记录已保存 Record Saved",
                            f"记录已保存！开始新的30分钟。\nRecord saved! New 30-min session starts now.\n\n"
                            f"记录位置 Saved to:\n{RECORDS_DIR}")
        self._schedule_next(self.INTERVAL_MINUTES)

    def _on_snooze(self):
        self.snooze_count += 1
        self._schedule_next(self.SNOOZE_MINUTES)

    def _open_records(self):
        ensure_records_dir()
        os.startfile(RECORDS_DIR)

    def run(self):
        self.root.mainloop()


# ─────────────────────────────────────────────
# 7. 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("正在加载假期数据... Loading holiday data...")
    HOLIDAYS = fetch_holiday_data()
    print(f"假期数据已加载 {len(HOLIDAYS)} 天 / {len(HOLIDAYS)} holiday days loaded.")

    today = datetime.date.today()
    status = "非工作日（可启动）" if is_holiday(today) else "工作日"
    print(f"今天 {today} 是：{status}")

    app = HolidayGuardian()
    app.run()
