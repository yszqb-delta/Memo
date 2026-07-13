from flask import Flask, render_template, request, redirect, url_for
from datetime import date, timedelta, datetime
from copy import deepcopy
import json
import sys
import os

app = Flask(__name__)
FILE = "memos.json"

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FILE = os.path.join(BASE_DIR, "memos.json")


# ==================== 工具函数 ====================
def read_json():
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def today():
    """统一今日日期接口（测试时只改这里）"""
    return date.today()


def reset_daily_tasks(data, today_str):
    for t in data["DailyTask"]:
        if t.get("Done") and t.get("DoneDate") and t["DoneDate"] < today_str:
            t["Done"] = False
            t["DoneDate"] = None


def trigger_timer_tasks(data, today_str):
    to_add = []
    remaining = []

    for tt in data["TimerTask"]:
        if tt["TriggerDate"] <= today_str:
            to_add.append({
                "TaskID": data["DailyID"],
                "Title": tt["Title"],
                "Info": tt["Info"],
                "Done": False,
                "DoneDate": None
            })
            data["DailyID"] += 1

            if tt["Repeat"] == "none":
                continue
            elif tt["Repeat"] == "daily":
                next_date = date.fromisoformat(tt["TriggerDate"]) + timedelta(days=1)
                tt["TriggerDate"] = str(next_date)
                remaining.append(tt)
            elif tt["Repeat"] == "weekly":
                next_date = date.fromisoformat(tt["TriggerDate"]) + timedelta(days=7)
                tt["TriggerDate"] = str(next_date)
                remaining.append(tt)
            elif tt["Repeat"] == "monthly":
                d = date.fromisoformat(tt["TriggerDate"])
                month = d.month + 1
                year = d.year
                if month > 12:
                    month = 1
                    year += 1
                day = min(d.day, [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30,
                                  31, 31, 30, 31, 30, 31][month - 1])
                tt["TriggerDate"] = str(date(year, month, day))
                remaining.append(tt)
            elif tt["Repeat"] == "yearly":
                d = date.fromisoformat(tt["TriggerDate"])
                tt["TriggerDate"] = str(d.replace(year=d.year + 1))
                remaining.append(tt)
        else:
            remaining.append(tt)

    if to_add:
        data["DailyTask"].extend(to_add)
    data["TimerTask"] = remaining


# ==================== 首页 ====================
@app.route("/")
def index():
    page = request.args.get("page", "today")
    today_str = str(today())

    data = read_json()

    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    timer_tasks = deepcopy(data["TimerTask"])
    for task in timer_tasks:
        d = datetime.strptime(task["TriggerDate"], "%Y-%m-%d")
        task["WeekDayText"] = weekdays[d.weekday()]

    reset_daily_tasks(data, today_str)
    trigger_timer_tasks(data, today_str)
    write_json(data)

    daily_tasks = [t for t in data["DailyTask"] if not t.get("Done", False)]
    all_done = (
            len(data["DailyTask"]) > 0 and
            len(daily_tasks) == 0
    )
    longterm_tasks = data["LongTermTask"]
    diary_list = []

    if page == "diary":
        diary_list = data["Diary"]
        diary_list.reverse()

    return render_template(
        "index.html",
        page=page,
        daily_tasks=daily_tasks,
        longterm_tasks=longterm_tasks,
        timer_tasks=timer_tasks,
        diary_list=diary_list,
        today=today_str,
        all_done=all_done
    )


# -------------------------每日任务：完成（局部刷新）--------------------------
@app.route("/api/finish_DailyTask/<int:task_id>")
def api_finish_DailyTask(task_id):
    data = read_json()
    today_str = str(today())

    for task in data["DailyTask"]:
        if task["TaskID"] == task_id:
            task["Done"] = True
            task["DoneDate"] = today_str
            break

    write_json(data)

    return render_template(
        "_daily_tasks.html",
        daily_tasks=[t for t in data["DailyTask"] if not t.get("Done")]
    )


# -------------------------每日任务：删除（局部刷新）--------------------------
@app.route("/api/delete_DailyTask/<int:task_id>")
def api_delete_DailyTask(task_id):
    data = read_json()
    data["DailyTask"] = [
        t for t in data["DailyTask"]
        if t["TaskID"] != task_id
    ]
    write_json(data)

    return render_template(
        "_daily_tasks.html",
        daily_tasks=[t for t in data["DailyTask"] if not t.get("Done")]
    )


# -------------------------每日任务：上移（局部刷新）--------------------------
@app.route("/api/move_up_DailyTask/<int:task_id>")
def api_move_up_DailyTask(task_id):
    data = read_json()
    tasks = data["DailyTask"]

    for i, t in enumerate(tasks):
        if t["TaskID"] == task_id and i > 0:
            tasks[i-1], tasks[i] = tasks[i], tasks[i-1]
            break

    write_json(data)
    return render_template("_daily_tasks.html", daily_tasks=data["DailyTask"])


# -------------------------每日任务：下移（局部刷新）--------------------------
@app.route("/api/move_down_DailyTask/<int:task_id>")
def api_move_down_DailyTask(task_id):
    data = read_json()
    tasks = data["DailyTask"]

    for i, t in enumerate(tasks):
        if t["TaskID"] == task_id and i < len(tasks) - 1:
            tasks[i+1], tasks[i] = tasks[i], tasks[i+1]
            break

    write_json(data)
    return render_template("_daily_tasks.html", daily_tasks=data["DailyTask"])


# -------------------------长期任务：完成（局部刷新）--------------------------
@app.route("/api/finish_LongTerm/<int:task_id>")
def api_finish_LongTerm(task_id):
    data = read_json()
    data["LongTermTask"] = [
        t for t in data["LongTermTask"]
        if t["TaskID"] != task_id
    ]
    write_json(data)
    return render_template(
        "_longterm_tasks.html",
        longterm_tasks=data["LongTermTask"]
    )


# -------------------------长期任务：上移（局部刷新）--------------------------
@app.route("/api/move_up_LongTerm/<int:task_id>")
def api_move_up_LongTerm(task_id):
    data = read_json()
    tasks = data["LongTermTask"]

    for i, t in enumerate(tasks):
        if t["TaskID"] == task_id and i > 0:
            tasks[i-1], tasks[i] = tasks[i], tasks[i-1]
            break

    write_json(data)
    return render_template("_longterm_tasks.html", longterm_tasks=data["LongTermTask"])


# -------------------------长期任务：下移（局部刷新）--------------------------
@app.route("/api/move_down_LongTerm/<int:task_id>")
def api_move_down_LongTerm(task_id):
    data = read_json()
    tasks = data["LongTermTask"]

    for i, t in enumerate(tasks):
        if t["TaskID"] == task_id and i < len(tasks) - 1:
            tasks[i+1], tasks[i] = tasks[i], tasks[i+1]
            break

    write_json(data)
    return render_template("_longterm_tasks.html", longterm_tasks=data["LongTermTask"])


# -------------------------定时任务：删除（全局刷新）--------------------------
@app.route("/delete_Timer/<int:task_id>")
def delete_Timer(task_id):
    data = read_json()
    data["TimerTask"] = [
        t for t in data["TimerTask"]
        if t["TaskID"] != task_id
    ]
    write_json(data)
    return redirect(url_for("index", page="today"))


# ==================== 添加页面（全部全局刷新） ====================
@app.route("/add_DailyTask", methods=["GET", "POST"])
def add_DailyTask():
    if request.method == "POST":
        data = read_json()
        data["DailyTask"].append({
            "TaskID": data["DailyID"],
            "Title": request.form["title"],
            "Info": request.form.get("info", ""),
            "Done": False,
            "DoneDate": None
        })
        data["DailyID"] += 1
        write_json(data)
        return redirect(url_for("index", page="today"))
    return render_template("add_DailyTask.html")


@app.route("/add_LongTerm", methods=["GET", "POST"])
def add_LongTerm():
    today_str = str(today())
    if request.method == "POST":
        data = read_json()
        data["LongTermTask"].append({
            "TaskID": data["LongTermID"],
            "Title": request.form["title"],
            "Info": request.form.get("info", ""),
            "StartDate": today_str,
            "Deadline": request.form["deadline"]
        })
        data["LongTermID"] += 1
        write_json(data)
        return redirect(url_for("index", page="today"))
    return render_template("add_LongTerm.html", today=today_str)


@app.route("/add_Diary", methods=["GET", "POST"])
def add_Diary():
    today_str = str(today())
    if request.method == "POST":
        data = read_json()
        data["Diary"].append({
            "DiaryID": data["DiaryID"],
            "Date": today_str,
            "Content": request.form["content"]
        })
        data["DiaryID"] += 1
        write_json(data)
        return redirect(url_for("index", page="diary"))
    return render_template("add_Diary.html")


@app.route("/add_Timer", methods=["GET", "POST"])
def add_Timer():
    today_str = str(today())
    if request.method == "POST":
        data = read_json()
        data["TimerTask"].append({
            "TaskID": data["TimerID"],
            "Title": request.form["title"],
            "Info": request.form.get("info", ""),
            "TriggerDate": request.form["trigger_date"],
            "Repeat": request.form.get("repeat", "none")
        })
        data["TimerID"] += 1
        write_json(data)
        return redirect(url_for("index", page="today"))
    return render_template("add_Timer.html", today=today_str)


# ==================== 修改页面（全部全局刷新） ====================
@app.route("/edit_DailyTask/<int:task_id>", methods=["GET", "POST"])
def edit_DailyTask(task_id):
    data = read_json()
    if request.method == "POST":
        for task in data["DailyTask"]:
            if task["TaskID"] == task_id:
                task["Title"] = request.form["title"]
                task["Info"] = request.form.get("info", "")
                break
        write_json(data)
        return redirect(url_for("index", page="today"))

    task = next((t for t in data["DailyTask"] if t["TaskID"] == task_id), None)
    return render_template("edit_DailyTask.html", task=task)


@app.route("/edit_LongTerm/<int:task_id>", methods=["GET", "POST"])
def edit_LongTerm(task_id):
    data = read_json()
    today_str = str(today())

    if request.method == "POST":
        for task in data["LongTermTask"]:
            if task["TaskID"] == task_id:
                task["Title"] = request.form["title"]
                task["Info"] = request.form.get("info", "")
                task["Deadline"] = request.form["deadline"]
                break
        write_json(data)
        return redirect(url_for("index", page="today"))

    task = next((t for t in data["LongTermTask"] if t["TaskID"] == task_id), None)
    return render_template("edit_LongTerm.html", task=task, today=today_str)


@app.route("/edit_Diary/<int:diary_id>", methods=["GET", "POST"])
def edit_Diary(diary_id):
    data = read_json()
    if request.method == "POST":
        for d in data["Diary"]:
            if d["DiaryID"] == diary_id:
                d["Content"] = request.form["content"]
                break
        write_json(data)
        return redirect(url_for("index", page="diary"))

    diary = next((d for d in data["Diary"] if d["DiaryID"] == diary_id), None)
    return render_template("edit_Diary.html", diary=diary)


@app.route("/edit_Timer/<int:task_id>", methods=["GET", "POST"])
def edit_Timer(task_id):
    data = read_json()
    if request.method == "POST":
        for task in data["TimerTask"]:
            if task["TaskID"] == task_id:
                task["Title"] = request.form["title"]
                task["Info"] = request.form.get("info", "")
                task["TriggerDate"] = request.form["trigger_date"]
                task["Repeat"] = request.form["repeat"]
                break
        write_json(data)
        return redirect(url_for("index", page="today"))

    task = next((t for t in data["TimerTask"] if t["TaskID"] == task_id), None)
    return render_template("edit_Timer.html", task=task)


# ==================== 启动 ====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
