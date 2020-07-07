from ..base import Monitor
from ..Utils import (
    timestamp,
    waittime,
)

from .YoutubeConstants import Headers

import json
import re
import requests
import time
from bs4 import BeautifulSoup as bs

# vip=tgt, word=title+description, standby_chat="True"/"False", standby_chat_onstart="True"/"False", no_chat="True"/"False", status_push="等待|开始|结束|上传|删除", regen="False"/"间隔秒数", regen_amount="1"/"恢复数量"
class YoutubeLive(Monitor):
    @staticmethod
    def getyoutubevideostatus(video_id, cookies, proxy):
        """
        删除:

        视频上传:"isLiveContent":false

        直播等待:"isLiveContent":true,"isLiveNow":false
        直播开始:"isLiveContent":true,"isLiveNow":true
        直播结束:"isLiveContent":true,"isLiveNow":false,"endTimestamp":

        首播等待:"isLiveContent":false,"isLiveNow":false
        首播开始:"isLiveContent":false,"isLiveNow":true
        首播结束:"isLiveContent":false,"isLiveNow":false,"endTimestamp":
        """
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            response = requests.get(
                url, headers=Headers, cookies=cookies, timeout=(3, 7), proxies=proxy
            )
            soup = bs(response.text, "lxml")
            script = soup.find(string=re.compile(r"\"isLiveContent\":"))
            if not script:
                video_status = "删除"
            elif '"isLiveNow":' in script:
                if '"endTimestamp":' in script:
                    video_status = "结束"
                elif '"isLiveNow":true' in script:
                    video_status = "开始"
                else:
                    video_status = "等待"
            else:
                video_status = "上传"
            return video_status
        except Exception as e:
            raise e

    @staticmethod
    def getyoutubevideodic(user_id, cookies, proxy):
        try:
            videodic = {}
            url = f"https://www.youtube.com/channel/{user_id}/videos?view=57&flow=grid"
            response = requests.get(
                url, headers=Headers, cookies=cookies, timeout=(3, 7), proxies=proxy
            )

            videolist_json = json.loads(
                re.findall(r"window\[\"ytInitialData\"\] = (.*?);", response.text)[0]
            )
            videolist = []

            def __search(key, json):
                for k in json:
                    if k == key:
                        videolist.append(json[k])
                    elif isinstance(json[k], dict):
                        __search(key, json[k])
                    elif isinstance(json[k], list):
                        for item in json[k]:
                            if isinstance(item, dict):
                                __search(key, item)
                return

            __search("gridVideoRenderer", videolist_json)
            for video_json in videolist:
                video_id = video_json["videoId"]
                video_title = video_json["title"]["simpleText"]
                if "publishedTimeText" in video_json:
                    video_type, video_status = "视频", "上传"
                    video_timestamp = timestamp()
                elif "upcomingEventData" in video_json:
                    status = video_json["thumbnailOverlays"][0][
                        "thumbnailOverlayTimeStatusRenderer"
                    ]["text"]["simpleText"]
                    if (
                        "首播" in status or "PREMIERE" in status or "プレミア" in status
                    ):  # 对语言敏感，在有cookies时以cookies设置的语言为准
                        video_type, video_status = "首播", "等待"
                    else:
                        video_type, video_status = "直播", "等待"
                    video_timestamp = video_json["upcomingEventData"]["startTime"]
                else:
                    status = video_json["badges"][0]["metadataBadgeRenderer"]["label"]
                    if "首播" in status or "PREMIERE" in status or "プレミア" in status:
                        video_type, video_status = "首播", "开始"
                    else:
                        video_type, video_status = "直播", "开始"
                    video_timestamp = timestamp()
                videodic[video_id] = {
                    "video_title": video_title,
                    "video_type": video_type,
                    "video_status": video_status,
                    "video_timestamp": video_timestamp,
                }

            """
            soup = BeautifulSoup(response.text, 'lxml')
            videolist_all = soup.find_all(class_='yt-lockup-content')
            for video in videolist_all:
                video_id = video.h3.a["href"].replace('/watch?v=', '')
                video_title = video.h3.a["title"]
                if len(video.find(class_="yt-lockup-meta-info").find_all("li")) > 1:
                    video_type, video_status = "视频", "上传"
                    video_timestamp = int(
                        datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).timestamp())
                else:
                    timestamp = video.find(attrs={"data-timestamp": True})
                    if video.find(class_="accessible-description"):
                        if timestamp:
                            video_type, video_status = "首播", "等待"
                            video_timestamp = timestamp["data-timestamp"]
                        else:
                            video_type, video_status = "首播", "开始"
                            video_timestamp = int(
                                datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).timestamp())
                    else:
                        if timestamp:
                            video_type, video_status = "直播", "等待"
                            video_timestamp = timestamp["data-timestamp"]
                        else:
                            video_type, video_status = "直播", "开始"
                            video_timestamp = int(
                                datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).timestamp())
                videodic[video_id] = {"video_title": video_title, "video_type": video_type,
                                    "video_status": video_status, "video_timestamp": video_timestamp}
            """
            return videodic
        except Exception as e:
            raise e

    @staticmethod
    def getyoutubevideodescription(video_id, cookies, proxy):
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            response = requests.get(
                url, headers=Headers, cookies=cookies, timeout=(3, 7), proxies=proxy
            )
            video_description = re.findall(
                r'\\"description\\":{\\"simpleText\\":\\"([^"]*)\\"', response.text
            )[0]
            video_description = video_description.replace("\\\\n", "\n").replace(
                "\\/", "/"
            )
            return video_description
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
        self.submonitorconfig_setname("youtubechat_submonitor_cfg")
        self.submonitorconfig_addconfig("youtubechat_config", self.cfg)

        self.is_firstrun = True
        # video_id为字符
        self.videodic = {}
        # 是否检测待机直播间的弹幕
        self.standby_chat = getattr(self, "standby_chat", "False")
        # 是否检测在第一次检测时已开启的待机直播间的弹幕
        self.standby_chat_onstart = getattr(self, "standby_chat_onstart", "False")
        # 不记录弹幕
        self.no_chat = getattr(self, "no_chat", "False")
        # 需要推送的情况，其中等待|开始|结束是直播和首播才有的情况，上传是视频才有的情况，删除则都存在
        self.status_push = getattr(self, "status_push", "等待|开始|结束|上传|删除")
        # 推送惩罚恢复间隔
        self.regen = getattr(self, "regen", "False")
        # 每次推送惩罚恢复量
        self.regen_amount = getattr(self, "regen_amount", 1)

    def run(self):
        while not self.stop_now:
            # 更新视频列表
            try:
                videodic_new = YoutubeLive.getyoutubevideodic(
                    self.tgt, self.cookies, self.proxy
                )
                for video_id in videodic_new:
                    if video_id not in self.videodic:
                        self.videodic[video_id] = videodic_new[video_id]
                        if (
                            not self.is_firstrun
                            or videodic_new[video_id]["video_status"] == "等待"
                            and self.standby_chat_onstart == "True"
                            or videodic_new[video_id]["video_status"] == "开始"
                        ):
                            self.push(video_id)
                if self.is_firstrun:
                    self.log_info(
                        f'"{self.name}" getyoutubevideodic {self.tgt}: {videodic_new}',
                    )
                    self.is_firstrun = False
                self.log_success(f'"{self.name}" getyoutubevideodic {self.tgt}',)
            except Exception as e:
                self.log_error(f'"{self.name}" getyoutubevideodic {self.tgt}: {e}',)

            # 更新视频状态
            for video_id in self.videodic:
                if (
                    self.videodic[video_id]["video_status"] == "等待"
                    or self.videodic[video_id]["video_status"] == "开始"
                ):
                    try:
                        video_status = YoutubeLive.getyoutubevideostatus(
                            video_id, self.cookies, self.proxy
                        )
                        if self.videodic[video_id]["video_status"] != video_status:
                            self.videodic[video_id]["video_status"] = video_status
                            self.push(video_id)
                        self.log_success(
                            f'"{self.name}" getyoutubevideostatus {video_id}',
                        )
                    except Exception as e:
                        self.log_error(
                            f'[Error] "{self.name}" getvideostatus {video_id}',
                        )
            time.sleep(self.interval)

    def push(self, video_id):
        if self.videodic[video_id]["video_status"] in self.status_push:
            # 获取视频简介
            try:
                video_description = YoutubeLive.getyoutubevideodescription(
                    video_id, self.cookies, self.proxy
                )
                self.log_success(
                    f'"{self.name}" getyoutubevideodescription {video_id}',
                )
            except Exception as e:
                self.log_error(
                    f'"{self.name}" getyoutubevideodescription {video_id}: {e}',
                )
                video_description = ""

            # 计算推送力度
            pushcolor_vipdic = Monitor.getpushcolordic(self.tgt, self.vip_dic)
            pushcolor_worddic = Monitor.getpushcolordic(
                f"{self.videodic[video_id]['video_title']}\n{video_description}",
                self.word_dic,
            )
            pushcolor_dic = Monitor.addpushcolordic(pushcolor_vipdic, pushcolor_worddic)

            # 进行推送
            if pushcolor_dic:
                pushtext = f"【{self.__class__.__name__} {self.tgt_name} {self.videodic[video_id]['video_type']}{self.videodic[video_id]['video_status']}】\n标题：{self.videodic[video_id]['video_title']}\n时间：{waittime(self.videodic[video_id]['video_timestamp'])}\n网址：https://www.youtube.com/watch?v={video_id}"
                self.pushall(pushtext, pushcolor_dic, self.push_list)
                self.log_info(
                    f'"{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',
                )

        if self.no_chat != "True":
            # 开始记录弹幕
            if (
                self.videodic[video_id]["video_status"] == "等待"
                and self.standby_chat == "True"
                or self.videodic[video_id]["video_status"] == "开始"
            ):
                monitor_name = f"{self.name} - YoutubeChat {video_id}"
                if (
                    monitor_name
                    not in getattr(self, self.submonitor_config_name)["submonitor_dic"]
                ):
                    self.submonitorconfig_addmonitor(
                        monitor_name,
                        "YoutubeChat",
                        video_id,
                        self.tgt_name,
                        "youtubechat_config",
                        tgt_channel=self.tgt,
                        interval=2,
                        regen=self.regen,
                        regen_amount=self.regen_amount,
                    )
                    self.checksubmonitor()
                    self.log_info(f'"{self.name}" startsubmonitor {monitor_name}',)
            # 停止记录弹幕
            else:
                monitor_name = f"{self.name} - YoutubeChat {video_id}" % (
                    self.name,
                    video_id,
                )
                if (
                    monitor_name
                    in getattr(self, self.submonitor_config_name)["submonitor_dic"]
                ):
                    self.submonitorconfig_delmonitor(monitor_name)
                    self.checksubmonitor()
                    self.log_info(f'"{self.name}" stopsubmonitor {monitor_name}',)
