from . import BaseMonitor
from .. import *
from ..Utils import Log

import copy
import time

# 保留cfg(cfg_mod并不修改cfg本身)，可以启动子监视器
class Monitor(BaseMonitor):
    @staticmethod
    def create(monitor_name, config):
        monitor_class = config["submonitor_dic"][monitor_name]["class"]
        monitor_target = config["submonitor_dic"][monitor_name]["target"]
        monitor_target_name = config["submonitor_dic"][monitor_name]["target_name"]
        monitor_config = config[config["submonitor_dic"][monitor_name]["config_name"]]
        monitor_config_mod = {}
        for key in config["submonitor_dic"][monitor_name].keys():
            if (
                key != "class"
                and key != "target"
                and key != "target_name"
                and key != "config_name"
            ):
                monitor_config_mod[key] = config["submonitor_dic"][monitor_name][key]
        monitor_thread = globals()[monitor_class](
            monitor_name,
            monitor_target,
            monitor_target_name,
            monitor_config,
            **monitor_config_mod,
        )
        monitor_thread.start()
        return monitor_thread

    # 初始化
    def __init__(self, name: str, tgt: str, tgt_name: str, cfg: dict, **cfg_mod):
        super().__init__(name, tgt, tgt_name, cfg, **cfg_mod)
        self.cfg = copy.deepcopy(cfg)

        self.submonitor_config_name = "cfg"
        self.submonitor_threads = {}
        self.submonitor_cnt = 0
        self.submonitor_live_cnt = 0
        self.submonitor_checknow = False

        self.stop_now = False

    # 重设submonitorconfig名字并初始化
    def submonitorconfig_setname(self, submonitor_config_name: str):
        self.submonitor_config_name = submonitor_config_name
        submonitor_config = getattr(
            self, submonitor_config_name, {"submonitor_dic": {}}
        )
        setattr(self, self.submonitor_config_name, submonitor_config)

    # 向submonitorconfig添加预设的config
    def submonitorconfig_addconfig(self, config_name: str, config: dict):
        submonitor_config = getattr(self, self.submonitor_config_name)
        submonitor_config[config_name] = config
        setattr(self, self.submonitor_config_name, submonitor_config)

    # 向submonitorconfig的submonitor_dic中添加子线程信息以启动子线程
    def submonitorconfig_addmonitor(
        self,
        monitor_name: str,
        monitor_class: str,
        monitor_target: str,
        monitor_target_name: str,
        monitor_config_name: str,
        **config_mod,
    ):
        submonitor_config = getattr(self, self.submonitor_config_name)
        if monitor_name not in submonitor_config["submonitor_dic"]:
            submonitor_config["submonitor_dic"][monitor_name] = {}
        submonitor_config["submonitor_dic"][monitor_name]["class"] = monitor_class
        submonitor_config["submonitor_dic"][monitor_name]["target"] = monitor_target
        submonitor_config["submonitor_dic"][monitor_name][
            "target_name"
        ] = monitor_target_name
        submonitor_config["submonitor_dic"][monitor_name][
            "config_name"
        ] = monitor_config_name
        for mod in config_mod:
            submonitor_config["submonitor_dic"][monitor_name][mod] = config_mod[mod]
        setattr(self, self.submonitor_config_name, submonitor_config)

    # 从submonitorconfig的submonitor_dic中删除对应的子线程
    def submonitorconfig_delmonitor(self, monitor_name: str):
        submonitor_config = getattr(self, self.submonitor_config_name)
        if monitor_name in submonitor_config["submonitor_dic"]:
            submonitor_config["submonitor_dic"].pop(monitor_name)
        setattr(self, self.submonitor_config_name, submonitor_config)

    # 按照submonitorconfig检查子线程池
    def checksubmonitor(self):
        if not self.submonitor_checknow:
            self.submonitor_checknow = True
            submonitorconfig = getattr(self, self.submonitor_config_name)
            if "submonitor_dic" in submonitorconfig:
                self.submonitor_cnt = len(submonitorconfig["submonitor_dic"])
                for monitor_name in submonitorconfig["submonitor_dic"]:
                    if monitor_name not in self.submonitor_threads:
                        # 按照submonitorconfig启动子线程并添加到子线程池
                        monitor_thread = Monitor.create(monitor_name, submonitorconfig)
                        self.submonitor_threads[monitor_name] = monitor_thread

                self.submonitor_live_cnt = 0
                for monitor_name in list(self.submonitor_threads):
                    if monitor_name not in submonitorconfig["submonitor_dic"]:
                        # 按照submonitorconfig关闭子线程并清理子线程池
                        if self.submonitor_threads[monitor_name].is_alive():
                            self.submonitor_threads[monitor_name].stop()
                            self.submonitor_live_cnt += 1
                        else:
                            self.submonitor_threads.pop(monitor_name)
                    else:
                        # 从子线程池检查并重启
                        if self.submonitor_threads[monitor_name].is_alive():
                            self.submonitor_threads[monitor_name].checksubmonitor()
                            self.submonitor_live_cnt += 1
                        else:
                            self.submonitor_threads[monitor_name].stop()
                            monitor_thread = Monitor.create(
                                monitor_name, submonitorconfig
                            )
                            self.submonitor_threads[monitor_name] = monitor_thread
                if self.submonitor_live_cnt > 0 or self.submonitor_cnt > 0:
                    Log(
                        f'[Check] "{self.name}" 子线程运行情况：{self.submonitor_live_cnt}/{self.submonitor_cnt}/'
                    )
            self.submonitor_checknow = False

    # 启动
    def run(self):
        self.checksubmonitor()
        while not self.stop_now:
            time.sleep(self.interval)

    # 停止线程
    def stop(self):
        self.stop_now = True
        for monitor_name in self.submonitor_threads:
            self.submonitor_threads[monitor_name].stop()
