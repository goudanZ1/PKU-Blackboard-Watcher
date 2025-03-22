import os
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.ini")
RECORD_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "record")
NOTICE_RECORD_PATH = os.path.join(RECORD_DIR, "notice_record.json")
ASSIGNMENT_RECORD_PATH = os.path.join(RECORD_DIR, "assignment_record.json")


def read_record_json(record_path: str) -> list[dict]:
    """读取记录文件"""
    with open(record_path, "r", encoding="utf-8") as file:
        record = json.load(file)
    return record


def write_record_json(record_path: str, record: list[dict]):
    """写入记录文件"""
    if not os.path.exists(RECORD_DIR):
        os.mkdir(RECORD_DIR)
    with open(record_path, "w", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False, indent=4)


def log(msg: str):
    """输出日志"""
    tz = pytz.timezone("Asia/Shanghai")
    dt = datetime.now(tz)
    print(f"[{dt.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def get_current_timestamp() -> int:
    """获得当前时间的毫秒级时间戳"""
    return int(datetime.now().timestamp()) * 1000


def convert_to_time(timestamp: int) -> str:
    """将毫秒级时间戳转换为可读的时间字符串"""
    tz = pytz.timezone("Asia/Shanghai")
    dt = datetime.fromtimestamp(timestamp / 1000, tz)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def convert_to_timestamp(time_str: str) -> int:
    """将 UTC 时间字符串转换为毫秒级时间戳"""
    tz = pytz.timezone("UTC")
    dt = tz.localize(datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%fZ"))
    return int(dt.timestamp()) * 1000


def convert_timezone(time_str: str) -> str:
    """将 UTC 时间字符串转换到东八区"""
    utc_tz = pytz.timezone("UTC")
    cn_tz = pytz.timezone("Asia/Shanghai")
    dt = utc_tz.localize(datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%fZ"))
    return dt.astimezone(cn_tz).strftime("%Y-%m-%d %H:%M:%S")


def test_within_hours(time_str: str, advance_hours: int) -> bool:
    """测试 time_str 所对应的时间是否在当前时间后的 advance_hours 小时之内"""
    current_timestamp = get_current_timestamp()
    target_timestamp = convert_to_timestamp(time_str)
    return target_timestamp - current_timestamp <= advance_hours * 3600000


def remove_suffix(course_name: str) -> str:
    """去除课程名的学期后缀"""
    pattern = r"\([^()]*\)$"
    return re.sub(pattern, "", course_name)


def parse_title(title_html: str) -> str:
    """提取通知标题中的有效信息，去除 “课程公告” “打开/拒绝” 等标签"""
    soup = BeautifulSoup(title_html, "html.parser")
    for tag in soup.find_all(class_="inlineContextMenu"):
        tag.decompose()
    for tag in soup.find_all(class_="announcementType"):
        tag.decompose()
    for tag in soup.find_all(class_="announcementPosted"):
        tag.decompose()
    return soup.get_text().strip()


def parse_content(content_html: str) -> str:
    """提取通知内容中的有效信息"""
    soup = BeautifulSoup(content_html, "html.parser")
    return soup.get_text().strip()


def has_attempted(assignment_html: str) -> bool:
    """根据上传作业页面的内容，判断用户是否已经提交过该作业"""
    soup = BeautifulSoup(assignment_html, "html.parser")
    return soup.find("title").get_text()[0] == "复"
    # return soup.find("div", id="currentAttempt") is not None


def parse_instruction(assignment_html: str) -> str:
    """提取上传作业页面中的作业要求（文字与附件）"""
    soup = BeautifulSoup(assignment_html, "html.parser")
    text_div = soup.find("div", class_="vtbegenerated")
    if text_div is None:
        text = ""
    else:
        text = text_div.get_text().strip()
        text_div.decompose()

    if soup.find("title").get_text()[0] == "复":  # 已提交过该作业
        info_div = soup.find("div", id="assignmentInfo")
        if info_div is not None:
            for index, tag in enumerate(info_div.find_all("a")):
                text += f"\n附件{index + 1}：{tag.get_text().strip()}"
    else:  # 未提交过该作业
        instructions_div = soup.find("li", id="instructions")
        if instructions_div is not None:
            for index, tag in enumerate(instructions_div.find_all("a")):
                text += f"\n附件{index + 1}：{tag.get_text().strip()}"

    return text
