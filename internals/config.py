import os
from configparser import ConfigParser
from internals.common import log, CONFIG_PATH


def get_config() -> tuple[dict, dict, dict, dict]:

    secret_names = ["iaaa_username", "iaaa_password", "email_address", "email_password", "sendkey"]
    secret_values = [os.getenv(name) for name in secret_names]
    # 如果 secrets.XX 未设置，在设置环境变量 xx: ${{ secrets.XX }} 时会传入空串，因此 os.getenv("xx") 得到空串而不是 None
    given_secrets = [name for name, value in zip(secret_names, secret_values) if len(value) > 0]
    log(f"Secrets given: {given_secrets}")

    if not os.path.exists(CONFIG_PATH):
        print("File config.ini not found in the project directory")
        exit(1)

    config = ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")

    iaaa_config = {
        "username": secret_values[0],
        "password": secret_values[1],
    }

    notify_config = {
        "method": config["notification"].get("method", ""),
        "email": secret_values[2],
        "password": secret_values[3],
        "sender": config["notification"].get("email_sender", ""),
        "sendkey": secret_values[4],
    }

    notice_config = {
        "notify_notice": config["notice"].getboolean("notify_notice", False),
        "title_prefix": config["notice"].get("title_prefix", "").replace("@", " "),
        "display_time": config["notice"].getboolean("display_time", True),
        "general_allowed_events": config["notice"].get("general_allowed_events", "123"),
        "specific_course_events": dict(config["notice:specific"]),
        "alias": dict(config["alias"]),
    }

    assignment_config = {
        "notify_assignment": config["assignment"].getboolean("notify_assignment", False),
        "advance_hours": config["assignment"].getint("advance_hours", 0),
        "title_prefix": config["assignment"].get("title_prefix", "").replace("@", " "),
        "display_time": config["assignment"].getboolean("display_time", True),
        "alias": dict(config["alias"]),
    }

    return iaaa_config, notify_config, notice_config, assignment_config
