import requests
from time import sleep
from .common import get_current_timestamp


class Blackboard:

    def __init__(self, iaaa_config: dict):
        self.username: str = iaaa_config["username"]
        self.password: str = iaaa_config["password"]
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            }
        )

    def login(self):
        """登录到教学网"""

        # IAAA 登录，响应头分配一个 iaaa.pku.edu.cn/ 下的 cookie JSESSIONID，响应体包含一个 token
        iaaa_response = self.session.post(
            "https://iaaa.pku.edu.cn/iaaa/oauthlogin.do",
            data={
                "appid": "blackboard",
                "userName": self.username,
                "password": self.password,
                "redirUrl": "http://course.pku.edu.cn/webapps/bb-sso-BBLEARN/execute/authValidate/campusLogin",
            },
        )

        try:
            iaaa_data = iaaa_response.json()
        except Exception as e:
            print(f"IAAA login exception: {e}")
            print(f"original response: \n{iaaa_response.text}")
            exit(1)

        if iaaa_data["success"]:
            token = iaaa_data["token"]
        else:
            print("IAAA login fail, please check your username and password in repository secrets")
            exit(1)

        # 教学网登录，响应头分配一个 course.pku.edu.cn/ 下的 cookie s_session_id
        campus_response = self.session.get(
            "http://course.pku.edu.cn/webapps/bb-sso-BBLEARN/execute/authValidate/campusLogin",
            params={
                "token": token,
            },
        )

    def get_notice_data(self) -> dict:
        """获取原始通知数据"""

        # 先 get 一下，响应头分配一个 course.pku.edu.cn/webapps/streamViewer 下的 cookie JSESSIONID
        view_response = self.session.get(
            "https://course.pku.edu.cn/webapps/streamViewer/streamViewer",
            params={
                "cmd": "view",
                "streamName": "alerts",
                "globalNavigation": "false",
            },
        )

        sleep(3)
        # 否则有可能返回空数据（可能的判断标准是 notice_data["sv_moreData"] 为 True）

        notice_response = self.session.post(
            "https://course.pku.edu.cn/webapps/streamViewer/streamViewer",
            data={
                "cmd": "loadStream",
                "streamName": "alerts",
                "providers": "{}",
                "forOverview": "false",
            },
        )

        try:
            notice_data = notice_response.json()
        except Exception as e:
            print(f"Get notice data exception: {e}")
            print(f"original response: \n{notice_response.text}")
            exit(1)

        return notice_data

    def get_calendar_data(self, advance_hours: int) -> list[dict]:
        """获取原始日程表数据，用于检测从现在开始的若干小时内有没有要截止的作业或事件"""

        current_timestamp = get_current_timestamp()

        calendar_response = self.session.get(
            "https://course.pku.edu.cn/webapps/calendar/calendarData/selectedCalendarEvents",
            params={
                "start": current_timestamp,
                "end": current_timestamp + advance_hours * 3600000,
                "course_id": "",
                "mode": "personal",
            },
        )

        try:
            calendar_data = calendar_response.json()
        except Exception as e:
            print(f"Get calendar data exception: {e}")
            print(f"original response: \n{calendar_response.text}")
            exit(1)

        return calendar_data

    def get_assignment_html_from_notice(self, uri: str) -> str:
        """由 notice entry 中的 uri 获取对应作业的上传页面"""

        assignment_response = self.session.get(f"https://course.pku.edu.cn{uri}")
        return assignment_response.text

    def get_assignment_html_from_calendar(self, calendar_id: str) -> str:
        """由 calendar_id 获取对应作业的上传页面"""

        assignment_response = self.session.get(
            f"https://course.pku.edu.cn/webapps/calendar/launch/attempt/{calendar_id}"
        )
        # 这个请求会重定向到对应作业的 /webapps/assignment/uploadAssignment 页面

        return assignment_response.text
