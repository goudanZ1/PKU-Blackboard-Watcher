import re
import requests
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from .common import log


class Notifier:

    def __init__(self, notify_config: dict):
        self.method: str = notify_config["method"]
        self.email: str = notify_config["email"]
        self.password: str = notify_config["password"]
        self.sender: str = notify_config["sender"]
        self.sendkey: str = notify_config["sendkey"]

    def notify_message(self, subject: str, body: str, tag: str = ""):
        """用 method 指定的方式向用户发送提醒消息"""

        if self.method == "email":
            self._email_notify(subject, body)
        elif self.method == "bark":
            self._bark_notify(subject, body, tag)
        elif self.method == "sct":
            notify_success = self._sct_notify(subject, body)
            if not notify_success:
                log(f"Ignore SCT notify failure and go on ({subject})")
                return
        elif self.method == "sc3":
            self._sc3_notify(subject, body, tag)
        else:
            print("The notification method must be 'email', 'bark', 'sc3' or 'sct'")
            print("Please check config.ini")
            exit(1)

        log(f"Successfully sended a notification message by {self.method}: {subject}")

    def _email_notify(self, subject: str, body: str):
        """登录到邮箱并给自己发送提醒邮件"""

        domain = self.email.split("@")[-1]
        if domain == "stu.pku.edu.cn":
            host = "smtphz.qiye.163.com"
        elif domain in {"pku.edu.cn", "qq.com", "163.com", "126.com"}:
            host = f"smtp.{domain}"
        else:
            print("Your email address must end with one of the following:")
            print("@stu.pku.edu.cn, @pku.edu.cn, @qq.com, @163.com, @126.com")
            print("Please check repository secrets")
            exit(1)

        message = MIMEText(body, "plain")
        message["From"] = formataddr((self.sender, self.email))
        message["To"] = self.email
        message["Subject"] = subject

        try:
            server = smtplib.SMTP_SSL(host, port=465)
            server.login(self.email, self.password)
            server.sendmail(self.email, self.email, message.as_string())
            server.quit()
        except Exception as e:
            print(f"Email notify fail: {e}")
            print("Please check your email address and password (authorization code) in repository secrets")
            exit(1)

    def _bark_notify(self, subject: str, body: str, tag: str):
        """向 Bark App 发推送"""

        response = requests.post(
            f"https://api.day.app/{self.sendkey}",
            data={
                "title": subject,
                "body": body,
                "group": tag,
                "badge": "1",  # 角标提醒
            },
        )

        try:
            response_data = response.json()
        except Exception as e:
            print(f"Bark notify exception: {e}")
            print(f"original response: \n{response.text}")
            exit(1)

        if response_data["code"] != 200:
            print(f"Bark notify fail: {response_data['message']}")
            print("Please check your Bark sendkey in repository secrets")
            exit(1)

    def _sct_notify(self, subject: str, body: str) -> bool:
        """使用 Server酱Turbo 通过微信服务号发送消息"""

        response = requests.post(
            f"https://sctapi.ftqq.com/{self.sendkey}.send",
            data={
                "title": subject,
                "desp": body.replace("\n", "\n\n"),  # desp 使用 Markdown 语法，两个换行符才是换行
                "noip": "1",  # 隐藏调用 IP
                "channel": "9",  # 指定消息通道为方糖服务号
            },
        )

        try:
            response_data = response.json()
        except Exception as e:
            print(f"SCT notify exception: {e}")
            print(f"original response: \n{response.text}")
            exit(1)

        if response_data["code"] != 0:
            print(f"SCT notify fail: {response_data['info']}")
            if response_data["code"] == 40001 and response_data["scode"] == 471:  # 超过发送次数限制
                # 认为这条记录已经处理过，回到主流程去保存记录文件
                # 每天的 5 条消息额度只用来发当天的消息，不用于发送积压消息
                return False
            else:
                print("Please check your SCT sendkey in repository secrets")
                exit(1)
        return True

    def _sc3_notify(self, subject: str, body: str, tag: str):
        """使用 Server酱3 发送消息"""

        # 从 sendkey 中提取 uid
        match = re.match(r"^sctp(\d+)t", self.sendkey)
        if match is None:
            print("SC3 notify fail: sendkey must follow a format like 'sctp{<number>}t...'")
            print("Please check your SC3 sendkey in repository secrets")
            exit(1)
        uid = match.group(1)

        response = requests.post(
            f"https://{uid}.push.ft07.com/send/{self.sendkey}.send",
            data={
                "title": subject,
                "desp": body.replace("\n", "\n\n"),  # desp 使用 Markdown 语法，两个换行符才是换行
                "short": body,  # 通知消息卡片的内容，这里提供原始消息内容，显示时会截取前若干个字符作为预览
                "tags": tag,
            },
        )

        try:
            response_data = response.json()
        except Exception as e:
            print(f"SC3 notify exception: {e}")
            print(f"original response: \n{response.text}")
            exit(1)

        if response_data["code"] != 0:
            print(f"SC3 notify fail: {response_data['error']}")
            print("Please check your SC3 sendkey in repository secrets")
            exit(1)
