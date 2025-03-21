from .common import *
from .blackboard import Blackboard
from .notifier import Notifier


class NoticeHandler:

    def __init__(self, notice_config: dict, blackboard: Blackboard, notifier: Notifier):
        self.is_init: str | None = None
        self.title_prefix: str = notice_config["title_prefix"]
        self.display_time: bool = notice_config["display_time"]
        self.allowed_events: str = notice_config["allowed_events"]  # "123"
        self.blocked_courses: list[str] = notice_config["blocked_courses"]
        self.alias: dict = notice_config["alias"]
        self.blackboard = blackboard
        self.notifier = notifier

    def filter_notice_info(self, entry: dict, course_dict: dict) -> dict:
        """从一个原始 notice entry 中提取有效信息，并整合为一条 record"""

        event = entry.get("extraAttribs", {}).get("event_type", "")
        content = parse_content(entry.get("se_details", ""))
        if not self.is_init and event == "AS:AS_AVAIL" and "se_itemUri" in entry:
            # 如果事件类型是作业可用，在 content 里加入作业要求和截止时间
            # 如果是 is_init 就没必要，这些记录都不会发送给用户
            assignment_html = self.blackboard.get_assignment_html_from_notice(entry["se_itemUri"])
            instruction = parse_instruction(assignment_html)
            if len(instruction) > 0:
                content += f"\n{instruction}"
            deadline_utc = entry["itemSpecificData"]["notificationDetails"].get("dueDate")
            if deadline_utc is not None:
                content += f"\n截止时间：{convert_timezone(deadline_utc)}"

        return {
            "id": entry["se_id"],
            "time": convert_to_time(entry["se_timestamp"]),
            "course": course_dict.get(entry.get("se_courseId"), ""),
            "title": parse_title(entry.get("se_context", "")),
            "content": content.strip(),
            "event": event,
        }

    def is_notify_allowed(self, record: dict) -> bool:
        """检查一个新的 notice record 是否符合用户的提醒配置"""

        if record["course"] in self.blocked_courses:
            return False

        event_type = record["event"]
        if event_type.startswith("AS"):
            return "1" in self.allowed_events
        elif event_type.startswith("CO"):
            return "2" in self.allowed_events
        else:
            return "3" in self.allowed_events

    def notify_notice(self, record: dict):
        """由 notice record 生成对应的消息标题与内容，并发送给用户"""

        # 生成消息标题和标签
        course = self.alias.get(record["course"].lower(), record["course"])
        # 读取 ini 文件时键名会自动转为小写，如果课程名里有大写字母需要先化成小写再匹配
        sep = "：" if len(course) > 0 else ""
        subject = self.title_prefix + course + sep + record["title"]

        # 生成消息内容
        body = record["content"]
        if self.display_time:
            body += f"\n发布时间：{record['time']}"

        self.notifier.notify_message(subject, body.strip(), tag=course)
        # 这里还要 strip 一下，防止 body 以换行符开头

    def do(self):
        """主函数"""

        # 1. 从教学网获取通知原始信息，并生成课程 id 到课程名的映射字典
        notice_data = self.blackboard.get_notice_data()

        course_list = notice_data.get("sv_extras", {}).get("sx_courses", [])
        course_dict = {course["id"]: remove_suffix(course["name"]) for course in course_list}

        # 2. 根据 record 文件是否存在来判断是否已经初始化，读取已在本地记录中的通知
        if os.path.exists(NOTICE_RECORD_PATH):
            old_notice_record = read_record_json(NOTICE_RECORD_PATH)
            self.is_init = False
        else:
            old_notice_record = []
            self.is_init = True

        old_notice_ids = {record["id"] for record in old_notice_record}

        # 3. 从所有通知中过滤出新的（本地没有记录的）通知，并提取通知信息
        updated_notice_record = []
        for entry in notice_data.get("sv_streamEntries", []):
            if entry["se_id"] not in old_notice_ids:
                updated_notice_record.append(self.filter_notice_info(entry, course_dict))

        # 4. 若程序第一次运行到这里（record 文件还不存在），则需要初始化，将本次检测到的通知作为
        #    初始数据保存在记录中；同时通知用户程序运行成功，顺便测试提醒消息能否正常发送
        if self.is_init:
            self.notifier.notify_message(
                "[GitHub] 通知提醒模块首次运行成功！",
                f"初始化已完成，从教学网同步了 {len(updated_notice_record)} 条已有通知。之后就可以自动检测新的通知并提醒您了~",
            )

        # 否则根据用户的屏蔽配置，选择性地对新通知进行提醒
        else:
            for record in updated_notice_record:
                if self.is_notify_allowed(record):
                    self.notify_notice(record)

        # 5. 如果配置没有问题、之前的流程都成功完成（没有中途 exit），更新现在已处理过的通知记录
        #   （由于用户屏蔽而没有提醒的通知也保存在记录中，以后不必再处理）
        if self.is_init or len(updated_notice_record) > 0:
            new_notice_record = old_notice_record + updated_notice_record
            write_record_json(NOTICE_RECORD_PATH, new_notice_record)
            log(f"Successfully processed {len(updated_notice_record)} notices")
