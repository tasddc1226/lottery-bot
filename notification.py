import requests
import re

class Notification:
    def send_lotto_buying_message(self, body: dict, webhook_url: str) -> None:
        assert type(webhook_url) == str

        result = body.get("result", {})
        if result.get("resultMsg", "FAILURE").upper() != "SUCCESS":  
            message = f"로또 구매 실패 (`{result.get('resultMsg', 'Unknown Error')}`) 남은잔액 : {body.get('balance', '확인불가')}"
            self._send_discord_webhook(webhook_url, message)
            return

        lotto_number_str = self.make_lotto_number_message(result["arrGameChoiceNum"])
        message = f"{result['buyRound']}회 로또 구매 완료 :moneybag: 남은잔액 : {body.get('balance', '확인불가')}\n```{lotto_number_str}```"
        self._send_discord_webhook(webhook_url, message)

    def make_lotto_number_message(self, lotto_number: list) -> str:
        assert type(lotto_number) == list

        # parse list without last number 3
        lotto_number = [x[:-1] for x in lotto_number]
        
        # remove alphabet and | replace white space  from lotto_number
        lotto_number = [x.replace("|", " ") for x in lotto_number]
        
        # lotto_number to string 
        lotto_number = '\n'.join(x for x in lotto_number)
        
        return lotto_number

    def send_win720_buying_message(self, body: dict, webhook_url: str) -> None:
        
        if body.get("resultCode") != '100':  
            message = f"연금복권 구매 실패 (`{body.get('resultMsg', 'Unknown Error')}`) 남은잔액 : {body.get('balance', '확인불가')}"
            self._send_discord_webhook(webhook_url, message)
            return       

        win720_round = body.get("round", "?")
        if win720_round == "?":
            try:
                 win720_round = body.get("saleTicket", "").split("|")[-2]
            except (IndexError, AttributeError, TypeError):
                 win720_round = "?"

        if not body.get("saleTicket"):
            win720_number_str = "번호 정보 없음"
        else:
            win720_number_str = self.make_win720_number_message(body.get("saleTicket"))

        message = f"{win720_round}회 연금복권 구매 완료 :moneybag: 남은잔액 : {body.get('balance', '확인불가')}\n```\n{win720_number_str}```"
        self._send_discord_webhook(webhook_url, message)

    def make_win720_number_message(self, win720_number: str) -> str:
        formatted_numbers = []
        for number in win720_number.split(","):
            formatted_number = f"{number[0]}조 " + " ".join(number[1:])
            formatted_numbers.append(formatted_number)
        return "\n".join(formatted_numbers)

    def send_lotto_winning_message(self, winning: dict, webhook_url: str) -> None: 
        assert type(winning) == dict
        assert type(webhook_url) == str

        balance_str = winning.get('balance', '확인불가')
        try: 
            round = winning["round"]
            money = winning["money"]

            if winning["lotto_details"]:
                max_label_status_length = max(len(f"{line['label']} {line['status']}") for line in winning["lotto_details"])

                formatted_lines = []
                for line in winning["lotto_details"]:
                    line_label_status = f"{line['label']} {line['status']}".ljust(max_label_status_length)
                    line_result = line["result"]
    
                    formatted_nums = []
                    for num in line_result:
                        raw_num = re.search(r'\d+', num).group()
                        formatted_num = f"{int(raw_num):02d}"
                        if '✨' in num:
                            formatted_nums.append(f"[{formatted_num}]")
                        else:
                            formatted_nums.append(f" {formatted_num} ")
    
                    formatted_nums = [f"{num:>6}" for num in formatted_nums]
    
                    formatted_line = f"{line_label_status} " + " ".join(formatted_nums)
                    formatted_lines.append(formatted_line)
    
                formatted_results = "\n".join(formatted_lines)
            else:
                formatted_results = "상세 정보를 불러오지 못했습니다."

            is_winning = winning['money'] != "-" and winning['money'] != "0 원" and winning['money'] != "0"
            
            if is_winning:
                winning_message = f"로또 *{winning['round']}회* - *{winning['money']}* 당첨 되었습니다 🎉 (남은잔액 : {balance_str})"
            else:
                winning_message = f"로또 *{winning['round']}회* - 다음 기회에... 🫠 (남은잔액 : {balance_str})"

            self._send_discord_webhook(webhook_url, f"```ini\n{formatted_results}```\n{winning_message}")
        except KeyError:
            message = f"로또 - 다음 기회에... 🫠 (남은잔액 : {balance_str})"
            self._send_discord_webhook(webhook_url, message)
            return

    def send_win720_winning_message(self, winning: dict, webhook_url: str) -> None: 
        assert type(winning) == dict
        assert type(webhook_url) == str

        balance_str = winning.get('balance', '확인불가')
        try:
            if "win720_details" in winning and winning["win720_details"]:
                max_label_status_length = max(len(f"{line['label']} {line['status']}") for line in winning["win720_details"])
                formatted_lines = []
                for line in winning["win720_details"]:
                    line_label_status = f"{line['label']} {line['status']}".ljust(max_label_status_length)
                    formatted_lines.append(f"{line_label_status} {line['result']}")
                
                formatted_results = "\n".join(formatted_lines)
                message_content = f"```ini\n{formatted_results}```\n"
            else:
                message_content = ""

            is_winning = winning['money'] != "-" and winning['money'] != "0 원" and winning['money'] != "0"

            if is_winning:
                message = f"{message_content}연금복권 *{winning['round']}회* - *{winning['money']}* 당첨 되었습니다 🎉 (남은잔액 : {balance_str})"
            else:
                 message = f"{message_content}연금복권 *{winning['round']}회* - 다음 기회에... 🫠 (남은잔액 : {balance_str})"

            self._send_discord_webhook(webhook_url, message)
        except KeyError:
            message = f"연금복권 - 다음 기회에... 🫠 (남은잔액 : {balance_str})"
            self._send_discord_webhook(webhook_url, message)

    def send_balance_warning(self, balance_str: str, threshold: int, webhook_url: str) -> None:
        message = (
            f"⚠️ 잔액 부족 경고\n"
            f"현재 잔액: `{balance_str}` (임계값: `{threshold:,}원`)\n"
            f"동행복권 사이트에서 예치금을 충전해 주세요."
        )
        self._send_discord_webhook(webhook_url, message)

    def _send_discord_webhook(self, webhook_url: str, message: str) -> None:
        if not webhook_url:
            print(f"[Info] Webhook URL not found. Message: {message}")
            return

        payload = { "content": message }
        requests.post(webhook_url, json=payload)
