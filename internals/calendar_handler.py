from .common import *
from .blackboard import Blackboard
from .notifier import Notifier


class CalendarHandler:

    def __init__(self, calendar_config: dict, blackboard: Blackboard, notifier: Notifier):
        self.advance_hours: int = calendar_config["advance_hours"]
        self.title_prefix: str = calendar_config["title_prefix"]
        self.display_time: bool = calendar_config["display_time"]
        self.alias: dict = calendar_config["alias"]
        self.blackboard = blackboard
        self.notifier = notifier

    def filter_assignment_info(self, entry: dict) -> dict:
        """从一个原始 assignment entry 中提取有效信息，并整合为一条 record"""

        id = entry["id"]
        time = convert_timezone(entry["endDate"])
        course = remove_suffix(entry["calendarName"])
        title = entry["title"]
        description = entry.get("description", "")
        should_notify = True  # 用户自定义的事件默认需要提醒

        # 如果该日程是一个作业 DDL：若用户已提交过该作业则不用提醒，否则在 description 里加入作业要求并提醒
        if course != "个人":
            assignment_html = self.blackboard.get_assignment_html_from_calendar(id)
            should_notify = not has_attempted(assignment_html)
            if should_notify:
                instruction = parse_instruction(assignment_html)
                if len(instruction) > 0:
                    description += f"\n{instruction}"

        return {
            "id": id,
            "time": time,
            "course": course,
            "title": title,
            "description": description.strip(),  # 防止 description 以换行符开头
            "should_notify": should_notify,
        }

    def notify_assignment(self, record: dict):
        """由 assignment record 生成对应的消息标题与内容，并发送给用户"""

        # 生成消息标题和标签
        if record["course"] == "个人":
            if "：" in record["title"]:
                course = record["title"].split("：")[0]
            else:
                course = "个人事件"
            subject = self.title_prefix + record["title"]
        else:
            course = self.alias.get(record["course"].lower(), record["course"])
            # 读取 ini 文件时键名会自动转为小写，如果课程名里有大写字母需要先化成小写再匹配
            sep = "：" if len(course) > 0 else ""
            subject = self.title_prefix + course + sep + record["title"]

        # 生成消息内容
        body = record["description"]
        if self.display_time:
            body += f"\n截止时间：{record['time']}"

        self.notifier.notify_message(subject, body.strip(), tag=course)
        # 这里还要 strip 一下，防止 body 以换行符开头

    def do(self):
        """主函数"""

        # 1. 查询从现在开始 advance_hours 小时内的所有日程（包括作业和用户自定义的事件）
        if self.advance_hours <= 0:
            print("'advance_hours' not a positive integer, please check config.ini")
            exit(1)
        calendar_data = self.blackboard.get_calendar_data(self.advance_hours)

        # 2. 从 record 文件读取已经处理过的日程
        if os.path.exists(ASSIGNMENT_RECORD_PATH):
            old_assignment_record = read_record_json(ASSIGNMENT_RECORD_PATH)
            is_init = False
        else:
            old_assignment_record = []
            is_init = True

        old_assignment_ids = {record["id"] for record in old_assignment_record}

        # 3. 从 calendar_data 这些即将到期的日程中，过滤出未处理过的日程，并提取日程信息
        updated_assignment_record = []
        for entry in calendar_data:
            if entry["id"] not in old_assignment_ids:
                updated_assignment_record.append(self.filter_assignment_info(entry))

        # 4. 若程序第一次运行到这里（record 文件还不存在），通知用户程序运行成功，顺便测试提醒消息
        #    能否正常发送（下一步中可能没有需要提醒的日程）
        if is_init:
            self.notifier.notify_message(
                "[GitHub] 日程提醒模块首次运行成功！",
                "之后就可以自动在作业、事件截止前提醒您了~",
            )

        # 5. 对用户自定义的事件和未提交过的作业进行提醒
        for record in updated_assignment_record:
            if record["should_notify"]:
                self.notify_assignment(record)
            else:
                log(f"Assignment ignored: {record['course']}-{record['title']}")

        # 6. 如果配置没有问题、之前的流程都成功完成（没有中途 exit），更新现在已处理过的日程记录
        #   （未提醒的只有已经提交过的作业，也保存在记录中，以后不必再处理）
        if is_init or len(updated_assignment_record) > 0:
            new_assignment_record = old_assignment_record + updated_assignment_record
            write_record_json(ASSIGNMENT_RECORD_PATH, new_assignment_record)
            log(f"Successfully processed {len(updated_assignment_record)} assignments")
