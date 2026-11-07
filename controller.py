import os
import sys
from dotenv import load_dotenv

import auth
import lotto645
import win720
import notification
from HttpClient import HttpClientSingleton
import time
import logging
import traceback


class _ErrorCounter(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.count = 0

    def emit(self, record):
        self.count += 1


logging.basicConfig(level=logging.WARNING, format="%(message)s")
_error_counter = _ErrorCounter()
logging.getLogger().addHandler(_error_counter)

# 작업 단위 실패 목록. 하나라도 있으면 프로세스를 exit code 1로 종료한다.
_failures = []


def _run_step(name: str, fn):
    """한 단계를 실행하고, 예외가 나면 기록만 하고 다음 단계로 넘어간다."""
    before = _error_counter.count
    try:
        ok = fn()
    except Exception as e:
        traceback.print_exc()
        print(f"[Error] {name} 실패: {e}")
        _failures.append(name)
        return
    if ok is False or _error_counter.count > before:
        print(f"[Error] {name} 실패 (결과 또는 로그 확인)")
        _failures.append(name)


def _lotto_buy_ok(response: dict) -> bool:
    result = response.get("result", {}) if isinstance(response, dict) else {}
    return str(result.get("resultMsg", "")).upper() == "SUCCESS"


def _win720_buy_ok(response: dict) -> bool:
    return isinstance(response, dict) and response.get("resultCode") == '100'


def _setup_and_login():
    load_dotenv(override=True)
    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if slack_webhook_url and slack_webhook_url.startswith("YOUR_"):
        slack_webhook_url = None

    discord_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if discord_webhook_url and discord_webhook_url.startswith("YOUR_"):
        discord_webhook_url = None

    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if telegram_bot_token and telegram_bot_token.startswith("YOUR_"):
        telegram_bot_token = None

    if slack_webhook_url:
        webhook_url = slack_webhook_url
    else:
        webhook_url = discord_webhook_url

    auth_ctrl = auth.AuthController()
    auth_ctrl.login(username, password)

    return auth_ctrl, username, webhook_url

def buy_lotto645(authCtrl: auth.AuthController, cnt: int, mode: str):
    lotto = lotto645.Lotto645()
    _mode = lotto645.Lotto645Mode[mode.upper()]
    response = lotto.buy_lotto645(authCtrl, cnt, _mode)
    response['balance'] = authCtrl.get_user_balance()
    return response

def check_winning_lotto645(authCtrl: auth.AuthController) -> dict:
    lotto = lotto645.Lotto645()
    item = lotto.check_winning(authCtrl)
    item['balance'] = authCtrl.get_user_balance()
    return item

def buy_win720(authCtrl: auth.AuthController, username: str):
    pension = win720.Win720()
    response = pension.buy_Win720(authCtrl, username)
    response['balance'] = authCtrl.get_user_balance()
    return response

def check_winning_win720(authCtrl: auth.AuthController) -> dict:
    pension = win720.Win720()
    item = pension.check_winning(authCtrl)
    item['balance'] = authCtrl.get_user_balance()
    return item

def _parse_balance(balance_str) -> int:
    if not isinstance(balance_str, str):
        return -1
    digits = ''.join(c for c in balance_str if c.isdigit())
    if not digits:
        return -1
    return int(digits)


def _maybe_send_balance_warning(balance_str, webhook_url: str) -> None:
    threshold_raw = os.environ.get('BALANCE_THRESHOLD', '').strip()
    if not threshold_raw:
        return
    try:
        threshold = int(threshold_raw)
    except ValueError:
        print(f"[Warn] BALANCE_THRESHOLD is not a valid integer: {threshold_raw!r}")
        return
    if threshold <= 0:
        return

    balance = _parse_balance(balance_str)
    if balance < 0:
        return
    if balance < threshold:
        notification.Notification().send_balance_warning(balance_str, threshold, webhook_url)


def send_message(mode: int, lottery_type: int, response: dict, webhook_url: str):
    notify = notification.Notification()

    if mode == 0:
        if lottery_type == 0:
            notify.send_lotto_winning_message(response, webhook_url)
        else:
            notify.send_win720_winning_message(response, webhook_url)
    elif mode == 1: 
        if lottery_type == 0:
            notify.send_lotto_buying_message(response, webhook_url)
        else:
            notify.send_win720_buying_message(response, webhook_url)

def check():
    auth_ctrl, _, webhook_url = _setup_and_login()
    last = {}

    def _lotto():
        response = check_winning_lotto645(auth_ctrl)
        send_message(0, 0, response=response, webhook_url=webhook_url)

    def _win720():
        response = check_winning_win720(auth_ctrl)
        send_message(0, 1, response=response, webhook_url=webhook_url)
        last['balance'] = response.get('balance')

    _run_step("로또 당첨 확인", _lotto)
    time.sleep(10)
    _run_step("연금복권 당첨 확인", _win720)

    _maybe_send_balance_warning(last.get('balance'), webhook_url)

def buy(): 
    load_dotenv(override=True) 
    count = int(os.environ.get('COUNT'))
    mode = "AUTO"
    last = {}

    def _lotto():
        auth_ctrl, _, webhook_url = _setup_and_login()
        last['webhook_url'] = webhook_url
        response = buy_lotto645(auth_ctrl, count, mode)
        send_message(1, 0, response=response, webhook_url=webhook_url)
        print(f"[Info] 로또 구매 결과: {response.get('result', {}).get('resultMsg')}")
        return _lotto_buy_ok(response)

    def _win720():
        HttpClientSingleton.get_instance().session.cookies.clear()
        auth_ctrl, username, webhook_url = _setup_and_login()
        last['webhook_url'] = webhook_url
        response = buy_win720(auth_ctrl, username)
        send_message(1, 1, response=response, webhook_url=webhook_url)
        print(f"[Info] 연금복권 구매 결과: {response.get('resultCode')} {response.get('resultMsg')}")
        last['balance'] = response.get('balance')
        return _win720_buy_ok(response)

    _run_step("로또 구매", _lotto)
    time.sleep(10)
    _run_step("연금복권 구매", _win720)

    _maybe_send_balance_warning(last.get('balance'), last.get('webhook_url'))

def lotto_buy():
    load_dotenv(override=True)
    count = int(os.environ.get('COUNT'))
    auth_ctrl, _, discord_webhook_url = _setup_and_login()
    mode = "AUTO"
    last = {}

    def _lotto():
        response = buy_lotto645(auth_ctrl, count, mode)
        send_message(1, 0, response=response, webhook_url=discord_webhook_url)
        last['balance'] = response.get('balance')
        return _lotto_buy_ok(response)

    _run_step("로또 구매", _lotto)
    _maybe_send_balance_warning(last.get('balance'), discord_webhook_url)

def win720_buy():
    auth_ctrl, username, discord_webhook_url = _setup_and_login()
    last = {}

    def _win720():
        response = buy_win720(auth_ctrl, username)
        send_message(1, 1, response=response, webhook_url=discord_webhook_url)
        last['balance'] = response.get('balance')
        return _win720_buy_ok(response)

    _run_step("연금복권 구매", _win720)
    _maybe_send_balance_warning(last.get('balance'), discord_webhook_url)

def lotto_check():
    auth_ctrl, _, discord_webhook_url = _setup_and_login()
    last = {}

    def _lotto():
        response = check_winning_lotto645(auth_ctrl)
        send_message(0, 0, response=response, webhook_url=discord_webhook_url)
        last['balance'] = response.get('balance')

    _run_step("로또 당첨 확인", _lotto)
    _maybe_send_balance_warning(last.get('balance'), discord_webhook_url)

def win720_check():
    auth_ctrl, _, discord_webhook_url = _setup_and_login()
    last = {}

    def _win720():
        response = check_winning_win720(auth_ctrl)
        send_message(0, 1, response=response, webhook_url=discord_webhook_url)
        last['balance'] = response.get('balance')

    _run_step("연금복권 당첨 확인", _win720)
    _maybe_send_balance_warning(last.get('balance'), discord_webhook_url)

def run():
    if len(sys.argv) < 2:
        print("Usage: python controller.py [buy|check]")
        return

    if sys.argv[1] == "buy":
        buy()
    elif sys.argv[1] == "check":
        check()
    elif sys.argv[1] == "buy_lotto":
        lotto_buy()
    elif sys.argv[1] == "buy_win720":
        win720_buy()
    elif sys.argv[1] == "check_lotto":
        lotto_check()
    elif sys.argv[1] == "check_win720":
        win720_check()
    else:
        print(f"Unknown command: {sys.argv[1]}")
        sys.exit(2)

    if _failures:
        print(f"[Error] 실패한 작업: {', '.join(_failures)}")
        sys.exit(1)

if __name__ == "__main__":
    run()
