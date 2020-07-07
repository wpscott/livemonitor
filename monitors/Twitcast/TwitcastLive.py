from ..base import Monitor
from ..Utils import (
    DateTimeFormat,
    now,
)

from urllib.parse import unquote
import time
import requests

# vip=tgt, "no_chat"="True"/"False", "status_push" = "开始|结束", regen="False"/"间隔秒数", regen_amount="1"/"恢复数量"
class TwitcastLive(Monitor):
    @staticmethod
    def gettwitcastlive(user_id, proxy):
        try:
            live_dic = {}
            url = f"https://twitcasting.tv/streamchecker.php?u={user_id}&v=999"
            response = requests.get(url, timeout=(3, 7), proxies=proxy)
            live = response.text.split("\t")
            live_id = live[0]
            if live_id:
                live_status = "开始"
            else:
                live_status = "结束"
            live_title = unquote(live[7])
            live_dic[live_id] = {"live_status": live_status, "live_title": live_title}
            return live_dic
        except Exception as e:
            raise e

    def __init__(self, name, tgt, tgt_name, cfg, **config_mod):
        super().__init__(name, tgt, tgt_name, cfg, **config_mod)

        # logpath = Path(f"./log/{self.__class__.__name__}")
        # self.logpath = logpath / f"{self.name}.txt"
        # if not logpath.exists():
        #     logpath.mkdir(parents=True)
        self.initialize_log(self.__class__.__name__, False, False)

        # 重新设置submonitorconfig用于启动子线程，并添加频道id信息到子进程使用的cfg中
        self.submonitorconfig_setname("twitcastchat_submonitor_cfg")
        self.submonitorconfig_addconfig("twitcastchat_config", self.cfg)

        self.livedic = {"": {"live_status": "结束", "live_title": ""}}
        self.no_chat = getattr(self, "no_chat", "False")
        self.status_push = getattr(self, "status_push", "开始|结束")
        self.regen = getattr(self, "regen", "False")
        self.regen_amount = getattr(self, "regen_amount", 1)

    def run(self):
        while not self.stop_now:
            # 获取直播状态
            try:
                livedic_new = TwitcastLive.gettwitcastlive(self.tgt, self.proxy)
                for live_id in livedic_new:
                    if (
                        live_id not in self.livedic
                        or livedic_new[live_id]["live_status"] == "结束"
                    ):
                        for live_id_old in self.livedic:
                            if self.livedic[live_id_old]["live_status"] != "结束":
                                self.livedic[live_id_old]["live_status"] = "结束"
                                self.push(live_id_old)

                    if live_id not in self.livedic:
                        self.livedic[live_id] = livedic_new[live_id]
                        self.push(live_id)
                    # 返回非空的live_id则必定为正在直播的状态，不过还是保留防止问题
                    elif (
                        self.livedic[live_id]["live_status"]
                        != livedic_new[live_id]["live_status"]
                    ):
                        self.livedic[live_id] = livedic_new[live_id]
                        self.push(live_id)
                self.log_success(f'"{self.name}" gettwitcastlive {self.tgt}')
            except Exception as e:
                self.log_error(f'"{self.name}" gettwitcastlive {self.tgt}: {e}',)
            time.sleep(self.interval)

    def push(self, live_id):
        live = self.livedic[live_id]
        if live["live_status"] in self.status_push:
            pushcolor_vipdic = Monitor.getpushcolordic(self.tgt, self.vip_dic)
            pushcolor_worddic = Monitor.getpushcolordic(
                live["live_title"], self.word_dic
            )
            pushcolor_dic = Monitor.addpushcolordic(pushcolor_vipdic, pushcolor_worddic)

            if pushcolor_dic:
                pushtext = f"【{self.__class__.__name__} {self.tgt_name} 直播{live['live_status']}】\n标题：{live['live_title']}\n时间：{now():DateTimeFormat}\n网址：https://twitcasting.tv/{self.tgt}"
                self.pushall(pushtext, pushcolor_dic, self.push_list)
                self.log_info(
                    f'"{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',
                )

        if self.no_chat != "True":
            monitor_name = f"{self.name} - TwitcastChat {live_id}"
            # 开始记录弹幕
            if live["live_status"] == "开始":
                if (
                    monitor_name
                    not in getattr(self, self.submonitor_config_name)["submonitor_dic"]
                ):
                    self.submonitorconfig_addmonitor(
                        monitor_name,
                        "TwitcastChat",
                        live_id,
                        self.tgt_name,
                        "twitcastchat_config",
                        tgt_channel=self.tgt,
                        interval=2,
                        regen=self.regen,
                        regen_amount=self.regen_amount,
                    )
                    self.checksubmonitor()
                    self.log_info(f'"{self.name}" startsubmonitor {monitor_name}',)
            # 停止记录弹幕
            else:
                if (
                    monitor_name
                    in getattr(self, self.submonitor_config_name)["submonitor_dic"]
                ):
                    self.submonitorconfig_delmonitor(monitor_name)
                    self.checksubmonitor()
                    self.log_info(f'"{self.name}" stopsubmonitor {monitor_name}',)
