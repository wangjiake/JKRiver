
from datetime import datetime
from agent.config import load_config
from agent.config.prompts import get_labels
from agent.core import SessionManager, run_cycle
from agent.storage import load_current_profile

def _print_log(level: str, msg: str):
    pass

def _print_cycle_details(result: dict, CL: dict):
    reply = result.get("response", "")
    if reply:
        print(reply)

def main():
    config = load_config()
    CL = get_labels("cli.labels", config.get("language", "zh"))
    manager = SessionManager(config)
    session = manager.get_or_create()

    profile = load_current_profile()

    try:
        while True:
            user_input = input("> ")
            if user_input.strip().lower() == "quit":
                break
            if not user_input.strip():
                continue
            result = run_cycle(user_input, session, log_fn=_print_log)
            _print_cycle_details(result, CL)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        from agent.sleep import run as sleep_run
        sleep_run()

if __name__ == "__main__":
    main()
