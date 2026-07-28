import re
from typing import Literal

from InquirerPy.prompts.input import InputPrompt
from InquirerPy.prompts.list import ListPrompt


def check_ip(ip: str) -> bool:
    regex = r"^((25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])$"
    return bool(re.search(regex, ip))


def ask_mode() -> Literal["local", "remote"]:
    return ListPrompt(
        message="How you want to configure raga ?",
        choices=[
            "Local",
            "Remote",
        ],
    ).execute().lower()

def ask_ip() -> str:
    while True:
        ip: str = InputPrompt(
            message="Configure ip address",
            default="127.0.0.1"
        ).execute()
        if check_ip(ip):
            return ip
        print("Ip address not valid")

def run_setup():
    mode = ask_mode()
    if mode == "local":
        ip = ask_ip()
        print(ip)