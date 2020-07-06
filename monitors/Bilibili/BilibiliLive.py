from ..base import Monitor
from ..Utils import DateTimeFormat, writelog, addpushcolordic, getpushcolordic, pushall

from datetime import datetime
from pathlib import Path
import requests
import time

# vip=tgt, "offline_chat"="True"/"False", "simple_mode"="True"/"False"/"合并数量", "no_chat"="True"/"False", "status_push" = "开始|结束", regen="False"/"间隔秒数", regen_amount="1"/"恢复数量"
class BilibiliLive(Monitor):
    @staticmethod
    def getbilibililivedic(room_id, proxy):
        try:
            live_dic = {}
            response = requests.get(
                f"http://api.live.bilibili.com/room/v1/Room/get_info?room_id={room_id}",
                timeout=(3, 7),
                proxies=proxy,
            )
            live = response.json()["data"]
            try:
                live_id = datetime.strptime(
                    live["live_time"] + " +0800", "%Y-%m-%d %H:%M:%S %z"
                ).timestamp()
            except:
                live_id = ""
            if live["live_status"] == 1:
                live_status = "开始"
            else:
                live_status = "结束"
            live_title = live["title"]
            live_dic[live_id] = {"live_status": live_status, "live_title": live_title}
            return live_dic
        except Exception as e:
            raise e

    def __init__(self, name, tgt, tgt_name, cfg, **config_mod):
        super().__init__(name, tgt, tgt_name, cfg, **config_mod)

        logpath = Path(f"./log/{self.__class__.__name__}")
        self.logpath = logpath / f"{self.name}.txt"
        if not logpath.exists():
            logpath.mkdir(parents=True)

        # 重新设置submonitorconfig用于启动子线程，并添加频道id信息到子进程使用的cfg中
        self.submonitorconfig_setname("bilibilichat_submonitor_cfg")
        self.submonitorconfig_addconfig("bilibilichat_config", self.cfg)

        self.livedic = {"": {"live_status": "结束", "live_title": ""}}
        self.offline_chat = getattr(self, "offline_chat", "False")
        self.simple_mode = getattr(self, "simple_mode", "False")
        self.no_chat = getattr(self, "no_chat", "False")
        self.status_push = getattr(self, "status_push", "开始|结束")
        self.regen = getattr(self, "regen", "False")
        self.regen_amount = getattr(self, "regen_amount", 1)

    def run(self):
        if self.offline_chat == "True" and self.no_chat != "True":
            monitor_name = f"{self.name} - BilibiliChat offline_chat"
            if (
                monitor_name
                not in getattr(self, self.submonitor_config_name)["submonitor_dic"]
            ):
                self.submonitorconfig_addmonitor(
                    monitor_name,
                    "BilibiliChat",
                    self.tgt,
                    self.tgt_name,
                    "bilibilichat_config",
                    simple_mode=self.simple_mode,
                )
                self.checksubmonitor()
            writelog(
                self.logpath, f'[Info] "{self.name}" startsubmonitor {monitor_name}'
            )

        while not self.stop_now:
            # 获取直播状态
            try:
                livedic_new = BilibiliLive.getbilibililivedic(self.tgt, self.proxy)
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
                    elif (
                        self.livedic[live_id]["live_status"]
                        != livedic_new[live_id]["live_status"]
                    ):
                        self.livedic[live_id] = livedic_new[live_id]
                        self.push(live_id)
                writelog(
                    self.logpath,
                    f'[Success] "{self.name}" getbilibililivedic {self.tgt}',
                )
            except Exception as e:
                writelog(
                    self.logpath,
                    f'[Error] "{self.name}" getbilibililivedic {self.tgt}: {e}',
                )
            time.sleep(self.interval)

    def push(self, live_id):
        live = self.livedic[live_id]
        if live["live_status"] in self.status_push:
            pushcolor_vipdic = getpushcolordic(self.tgt, self.vip_dic)
            pushcolor_worddic = getpushcolordic(live["live_title"], self.word_dic)
            pushcolor_dic = addpushcolordic(pushcolor_vipdic, pushcolor_worddic)

            if pushcolor_dic:
                pushtext = f"【{self.__class__.__name__} {self.tgt_name} 直播{live['live_status']}】\n标题：{live['live_title']}\n时间：{datetime.utcfromtimestamp(live_id):DateTimeFormat}\n网址：https://live.bilibili.com/{self.tgt}"
                pushall(pushtext, pushcolor_dic, self.push_list)
                writelog(
                    self.logpath,
                    f'[Info] "{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',
                )

        if self.offline_chat != "True" and self.no_chat != "True":
            monitor_name = f"{self.name} - BilibiliChat {live_id}" % (
                self.name,
                live_id,
            )
            # 开始记录弹幕
            if live["live_status"] == "开始":
                if (
                    monitor_name
                    not in getattr(self, self.submonitor_config_name)["submonitor_dic"]
                ):
                    self.submonitorconfig_addmonitor(
                        monitor_name,
                        "BilibiliChat",
                        self.tgt,
                        self.tgt_name,
                        "bilibilichat_config",
                        simple_mode=self.simple_mode,
                        regen=self.regen,
                        regen_amount=self.regen_amount,
                    )
                    self.checksubmonitor()
                writelog(
                    self.logpath, '[Info] "{self.name}" startsubmonitor {monitor_name}'
                )
            # 停止记录弹幕
            else:
                if (
                    monitor_name
                    in getattr(self, self.submonitor_config_name)["submonitor_dic"]
                ):
                    self.submonitorconfig_delmonitor(monitor_name)
                    self.checksubmonitor()
                    writelog(
                        self.logpath,
                        '[Info] "{self.name}" stopsubmonitor {monitor_name}',
                    )
