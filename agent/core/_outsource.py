"""Shared constants and helpers for outsource/dispatch_task integration in the core pipeline."""

import re

# Trigger keywords that prefix outsource task descriptions — stripped before passing to dispatch_task
OUTSOURCE_TRIGGER_RE = re.compile(
    r'^(外包模式|外包任务|帮我外包|用外包|outsource mode|outsource this|外包给ai|外包给你'
    r'|delegate to agent|run as task|use task agent|派遣モード|派遣して|派遣タスク|派遣に)[：:：\s]*',
    re.IGNORECASE,
)

# Keywords that indicate the user wants to resume a suspended outsource task
OUTSOURCE_RESUME_KEYWORDS = [
    "继续执行", "继续任务", "继续外包", "恢复任务",
    "resume task", "resume the task",
    "再開して", "タスクを再開",
]

# Short confirmation words that may mean "yes, start the pending outsource task"
OUTSOURCE_CONFIRM_WORDS = {
    "是", "好", "开始", "确认", "ok", "yes", "好的", "行", "嗯", "可以", "start", "confirm",
}
