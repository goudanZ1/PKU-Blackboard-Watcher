from internals.common import log
from internals.config import get_config
from internals.blackboard import Blackboard
from internals.notifier import Notifier
from internals.notice_handler import NoticeHandler
from internals.calendar_handler import CalendarHandler

if __name__ == "__main__":

    log("Program started")

    iaaa_config, notify_config, notice_config, assignment_config = get_config()

    blackboard = Blackboard(iaaa_config)
    blackboard.login()
    notifier = Notifier(notify_config)

    if notice_config["notify_notice"]:
        NoticeHandler(notice_config, blackboard, notifier).do()
    if assignment_config["notify_assignment"]:
        CalendarHandler(assignment_config, blackboard, notifier).do()

    log("Program completed")
