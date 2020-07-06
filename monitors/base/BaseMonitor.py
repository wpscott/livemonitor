import threading
import time
from pathlib import Path

# 仅从cfg和cfg_mod中获取参数，不会启动子监视器
class BaseMonitor(threading.Thread):
    def __init__(self, name: str, tgt: str, tgt_name: str, cfg: dict, **cfg_mod):
        super().__init__()
        self.name = name
        self.tgt = tgt
        self.tgt_name = tgt_name

        self.interval = 60
        self.vip_dic = {}
        self.word_dic = {}
        self.cookies = {}
        self.proxy = {}
        self.push_list = []
        # 不要直接修改通过cfg引用传递定义的列表和变量，请deepcopy后再修改
        for var in cfg:
            setattr(self, var, cfg[var])
        for var in cfg_mod:
            setattr(self, var, cfg_mod[var])

        self.stop_now = False

    def initialize_log(
        self, cls_name: str, sub_dir: bool = False, has_chat: bool = False
    ):
        logpath = Path(f"./log/{cls_name}")
        if sub_dir:
            logpath = logpath / self.tgt_name

        self.logpath = logpath / f"{self.name}.txt"
        if has_chat:
            self.chatpah = logpath / f"{self.name}_chat.txt"
        if not logpath.exists():
            logpath.mkdir(parents=True)

    def checksubmonitor(self):
        pass

    def run(self):
        while not self.stop_now:
            time.sleep(self.interval)

    def stop(self):
        self.stop_now = True
