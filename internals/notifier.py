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
        self.status: int = 0  # 0 为发送成功, 1 为发送失败，2 为超过发送次数限制

    def notify_message(self, subject: str, body: str, tag: str = ""):
        """用 method 指定的方式向用户发送提醒消息"""

        if self.status != 2:  # self.status == 0
            if self.method == "email":
                self._email_notify(subject, body)
            elif self.method == "bark":
                self._bark_notify(subject, body, tag)
            elif self.method == "sct":
                self._sct_notify(subject, body)
            elif self.method == "sc3":
                self._sc3_notify(subject, body, tag)
            else:
                log("The notification method must be 'email', 'bark', 'sc3' or 'sct'")
                log("Please check config.ini")
                self.status = 1

        if self.status == 0:
            log(f"Successfully sended a notification message by {self.method}: {subject}")
        elif self.status == 1:
            log(f"Failed to send the notification message by {self.method}: {subject}")
            exit(1)
        else:
            log(f"SCT limit reached, ignore notify failure and go on: {subject}")

    def _email_notify(self, subject: str, body: str):
        """登录到邮箱并给自己发送提醒邮件"""

        domain = self.email.split("@")[-1]
        if domain == "stu.pku.edu.cn":
            host = "smtphz.qiye.163.com"
        elif domain in {"pku.edu.cn", "qq.com", "163.com", "126.com"}:
            host = f"smtp.{domain}"
        else:
            log("Your email address must end with one of the following:")
            log("@stu.pku.edu.cn, @pku.edu.cn, @qq.com, @163.com, @126.com")
            log("Please check repository secrets")
            self.status = 1
            return

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
            log(f"Email notify failed: {e}")
            log("Please check your email address and password (authorization code) in repository secrets")
            self.status = 1

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
            log(f"Bark notify exception: {e}")
            log(f"original response: \n{response.text}")
            self.status = 1
            return

        if response_data["code"] != 200:
            log(f"Bark notify failed: {response_data['message']}")
            log("Please check your Bark sendkey in repository secrets")
            self.status = 1

    def _sct_notify(self, subject: str, body: str):
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
            log(f"SCT notify exception: {e}")
            log(f"original response: \n{response.text}")
            self.status = 1
            return

        if response_data["code"] != 0:
            log(f"SCT notify failed: {response_data['info']}")
            if response_data["code"] == 40001 and response_data["scode"] == 471:  # 超过发送次数限制
                # 忽略发送失败，仍然认为这条记录已经处理过，回到主流程去保存记录文件
                # 每天的 5 条消息额度只用来发当天的消息，不用于发送积压消息
                self.status = 2
            else:
                log("Please check your SCT sendkey in repository secrets")
                self.status = 1

    def _sc3_notify(self, subject: str, body: str, tag: str):
        """使用 Server酱3 发送消息"""

        # 从 sendkey 中提取 uid
        match = re.match(r"^sctp(\d+)t", self.sendkey)
        if match is None:
            log("SC3 notify failed: sendkey must follow a format like 'sctp{<number>}t...'")
            log("Please check your SC3 sendkey in repository secrets")
            self.status = 1
            return
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
            log(f"SC3 notify exception: {e}")
            log(f"original response: \n{response.text}")
            self.status = 1
            return

        if response_data["code"] != 0:
            log(f"SC3 notify failed: {response_data['error']}")
            log("Please check your SC3 sendkey in repository secrets")
            self.status = 1
