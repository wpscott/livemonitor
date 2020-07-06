from ..BaseMonitor import BaseMonitor
from ..Utils import (
    DateTimeFormat,
    timestamp,
    writelog,
    addpushcolordic,
    getpushcolordic,
    pushall,
)

from datetime import datetime
from pathlib import Path
import requests
import time
import json
import struct
import zlib
import threading
import websocket

# vip=userid, word=text, punish=tgt+push(不包括含有'vip'的类型), 获取弹幕的websocket连接只能使用http proxy
class BilibiliChat(BaseMonitor):
    @staticmethod
    def getbilibilichathostlist(proxy):
        hostlist = []
        try:
            response = requests.get(
                "https://api.live.bilibili.com/room/v1/Danmu/getConf", proxies=proxy
            )
            hostserver_list = response.json()["data"]["host_server_list"]
            for hostserver in hostserver_list:
                hostlist.append(
                    f'wss://{hostserver["host"]}:{hostserver["wss_port"]}/sub'
                )
            if hostlist:
                return hostlist
            else:
                raise Exception("Invalid hostlist")
        except Exception as e:
            raise e

    def __init__(self, name, tgt, tgt_name, cfg, **config_mod):
        super().__init__(name, tgt, tgt_name, cfg, **config_mod)

        logpath = Path(f"./log/{self.__class__.__name__}/{self.tgt_name}")
        self.logpath = logpath / f"{self.name}.txt"
        self.chatpah = logpath / f"{self.name}_chat.txt"
        if not logpath.exists():
            logpath.mkdir(parents=True)

        self.simple_mode = getattr(self, "simple_mode", "False")
        if self.simple_mode != "False":
            self.pushcount = 0
            self.pushtext_old = ""
            # self.pushtext_old = "【%s %s】\n" % (self.__class__.__name__, self.tgt_name)
            self.pushcolor_dic_old = {}
            try:
                self.simple_mode = int(self.simple_mode)
                if self.simple_mode == 0:
                    self.simple_mode = 1
            except:
                self.simple_mode = 1
        self.proxyhost = ""
        self.proxyport = ""
        if "http" in self.proxy:
            self.proxyhost = self.proxy["http"].split(":")[-2].replace("/", "")
            self.proxyport = self.proxy["http"].split(":")[-1]

        self.hostlist = []
        self.hostcount = 1
        self.ws = False
        self.is_linked = False
        self.pushpunish = {}
        self.regen_time = 0
        self.regen = getattr(self, "regen", "False")
        self.regen_amount = getattr(self, "regen_amount", 1)

    def getpacket(self, data, operation):
        """
        packet_length, header_length, protocol_version, operation, sequence_id

        HANDSHAKE=0, HANDSHAKE_REPLY = 1, HEARTBEAT = 2, HEARTBEAT_REPLY = 3, SEND_MSG = 4
        SEND_MSG_REPLY = 5, DISCONNECT_REPLY = 6, AUTH = 7, AUTH_REPLY = 8
        RAW = 9, PROTO_READY = 10, PROTO_FINISH = 11, CHANGE_ROOM = 12
        CHANGE_ROOM_REPLY = 13, REGISTER = 14, REGISTER_REPLY = 15, UNREGISTER = 16, UNREGISTER_REPLY = 17
        """
        body = json.dumps(data).encode("utf-8")
        header = struct.pack(">I2H2I", 16 + len(body), 16, 1, operation, 1)
        return header + body

    def prasepacket(self, packet):
        try:
            packet = zlib.decompress(packet[16:])
        except:
            pass

        packetlist = []
        offset = 0
        while offset < len(packet):
            try:
                header = packet[offset : offset + 16]
                headertuple = struct.Struct(">I2H2I").unpack_from(header)
                packet_length = headertuple[0]
                operation = headertuple[3]

                body = packet[offset + 16 : offset + packet_length]
                try:
                    data = json.loads(body.decode("utf-8"))
                    packetlist.append({"data": data, "operation": operation})
                except:
                    packetlist.append({"data": body, "operation": operation})

                offset += packet_length
            except:
                continue
        return packetlist

    def heartbeat(self):
        while not self.stop_now:
            if self.is_linked:
                self.ws.send(self.getpacket({}, 2))
                time.sleep(30)
            else:
                time.sleep(1)

    def parsedanmu(self, chat_json):
        try:
            chat_cmd = chat_json["cmd"]
            """
            if chat_cmd == 'LIVE': # 直播开始
            if chat_cmd == 'PREPARING': # 直播停止
            if chat_cmd == 'WELCOME':
                chat_user = chat_json['data']['uname']
            """
            if chat_cmd == "DANMU_MSG":
                chat_type = "message"
                chat_text = chat_json["info"][1]
                chat_userid = str(chat_json["info"][2][0])
                chat_username = chat_json["info"][2][1]
                chat_timestamp_float = float(chat_json["info"][0][4]) / 1000
                # chat_isadmin = dic['info'][2][2] == '1'
                # chat_isvip = dic['info'][2][3] == '1'
                chat = {
                    "chat_type": chat_type,
                    "chat_text": chat_text,
                    "chat_userid": chat_userid,
                    "chat_username": chat_username,
                    "chat_timestamp_float": chat_timestamp_float,
                }
                self.push(chat)
            elif chat_cmd == "SEND_GIFT":
                chat_type = (
                    f'gift {chat_json["data"]["giftName"]} {chat_json["data"]["num"]}'
                )
                chat_text = ""
                chat_userid = str(chat_json["data"]["uid"])
                chat_username = chat_json["data"]["uname"]
                chat_timestamp_float = float(chat_json["data"]["timestamp"])
                chat = {
                    "chat_type": chat_type,
                    "chat_text": chat_text,
                    "chat_userid": chat_userid,
                    "chat_username": chat_username,
                    "chat_timestamp_float": chat_timestamp_float,
                }
                self.push(chat)
            elif chat_cmd == "SUPER_CHAT_MESSAGE":
                chat_type = f'superchat CN¥{chat_json["data"]["price"]}'
                chat_text = chat_json["data"]["message"]
                chat_userid = str(chat_json["data"]["uid"])
                chat_username = chat_json["data"]["user_info"]["uname"]
                chat_timestamp_float = float(chat_json["data"]["start_time"])
                chat = {
                    "chat_type": chat_type,
                    "chat_text": chat_text,
                    "chat_userid": chat_userid,
                    "chat_username": chat_username,
                    "chat_timestamp_float": chat_timestamp_float,
                }
                self.push(chat)
        except:
            pass

    def on_open(self):
        # 未登录uid则为0，注意int和str类有区别，protover为1则prasepacket中无需用zlib解压
        auth_data = {
            "uid": 0,
            "roomid": int(self.tgt),
            "protover": 2,
            "platform": "web",
            "clientver": "1.10.3",
            "type": 2,
            "key": requests.get(
                "https://api.live.bilibili.com/room/v1/Danmu/getConf",
                proxies=self.proxy,
            ).json()["data"]["token"],
        }
        self.ws.send(self.getpacket(auth_data, 7))
        writelog(self.logpath, f'[Start] "{self.name}" connect {self.tgt}')

    def on_message(self, message):
        packetlist = self.prasepacket(message)

        for packet in packetlist:
            if packet["operation"] == 8:
                self.is_linked = True
                writelog(self.logpath, f'[Success] "{self.name}" connected {self.tgt}')

            if packet["operation"] == 5:
                if isinstance(packet["data"], dict):
                    self.parsedanmu(packet["data"])

    def on_error(self, error):
        writelog(self.logpath, f'[Error] "{self.name}" error {self.tgt}: {error}')

    def on_close(self):
        # 推送剩余的弹幕
        if self.simple_mode != "False":
            if self.pushtext_old:
                pushall(self.pushtext_old, self.pushcolor_dic_old, self.push_list)
                writelog(
                    self.logpath,
                    f'[Info] "{self.name}" pushall {str(self.pushcolor_dic_old)}\n{self.pushtext_old}',
                )

                self.pushtext_old = ""
                # self.pushtext_old = "【%s %s】\n" % (self.__class__.__name__, self.tgt_name)

        self.is_linked = False
        writelog(self.logpath, f'[Stop] "{self.name}" disconnect {self.tgt}')

    def run(self):
        # 启动heartbeat线程
        heartbeat_thread = threading.Thread(target=self.heartbeat, args=())
        heartbeat_thread.Daemon = True
        heartbeat_thread.start()

        while not self.stop_now:
            if self.hostcount < len(self.hostlist):
                host = self.hostlist[self.hostcount]
                self.hostcount += 1

                self.ws = websocket.WebSocketApp(
                    host,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                )
                self.ws.run_forever(
                    http_proxy_host=self.proxyhost, http_proxy_port=self.proxyport
                )
                time.sleep(1)
            else:
                try:
                    self.hostlist = BilibiliChat.getbilibilichathostlist(self.proxy)
                    self.hostcount = 0
                    writelog(
                        self.logpath,
                        f'[Info] "{self.name}" getbilibilichathostlist {self.tgt}: {self.hostlist}',
                    )
                    writelog(
                        self.logpath,
                        f'[Success] "{self.name}" getbilibilichathostlist {self.tgt}',
                    )
                except Exception as e:
                    writelog(
                        self.logpath,
                        f'[Error] "{self.name}" getbilibilichathostlist {self.tgt}: {e}',
                    )
                    time.sleep(5)

    def push(self, chat):
        writelog(
            self.chatpath,
            f'{chat["chat_timestamp_float"]}\t{chat["chat_username"]}\t{chat["chat_userid"]}\t{chat["chat_type"]}\t{chat["chat_text"]}',
        )

        pushcolor_vipdic = getpushcolordic(chat["chat_userid"], self.vip_dic)
        pushcolor_worddic = getpushcolordic(chat["chat_text"], self.word_dic)
        pushcolor_dic = addpushcolordic(pushcolor_vipdic, pushcolor_worddic)

        if pushcolor_dic:
            pushcolor_dic = self.punish(pushcolor_dic)

            if self.simple_mode == "False":
                pushtext = f"【{self.__class__.__name__} {self.tgt_name} 直播评论】\n用户：{chat['chat_username']}({chat['chat_userid']})\n内容：{chat['chat_text']}\n类型：{chat['chat_type']}\n时间：{datetime.utcfromtimestamp(chat['chat_timestamp_float']):DateTimeFormat}\n网址：https://live.bilibili.com/{self.tgt}"
                pushall(pushtext, pushcolor_dic, self.push_list)
                writelog(
                    self.logpath,
                    f'[Info] "{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',
                )
            else:
                self.pushcount += 1
                self.pushtext_old += chat["chat_text"]
                for color in pushcolor_dic:
                    if color in self.pushcolor_dic_old:
                        if self.pushcolor_dic_old[color] < pushcolor_dic[color]:
                            self.pushcolor_dic_old[color] = pushcolor_dic[color]
                    else:
                        self.pushcolor_dic_old[color] = pushcolor_dic[color]

                if self.pushcount % self.simple_mode == 0:
                    pushall(self.pushtext_old, self.pushcolor_dic_old, self.push_list)
                    writelog(
                        self.logpath,
                        f'[Info] "{self.name}" pushall {str(self.pushcolor_dic_old)}\n{self.pushtext_old}',
                    )
                    self.pushtext_old = ""
                    # self.pushtext_old = "【%s %s】\n" % (self.__class__.__name__, self.tgt_name)
                    self.pushcolor_dic_old = {}
                else:
                    self.pushtext_old += "\n"

    def punish(self, pushcolor_dic):
        if self.regen != "False":
            time_now = timestamp()
            regen_amt = int(
                int((time_now - self.regen_time) / float(self.regen))
                * float(self.regen_amount)
            )
            if regen_amt:
                self.regen_time = time_now
                for color in list(self.pushpunish):
                    if self.pushpunish[color] > regen_amt:
                        self.pushpunish[color] -= regen_amt
                    else:
                        self.pushpunish.pop(color)

        if self.tgt in self.vip_dic:
            for color in self.vip_dic[self.tgt]:
                if color in pushcolor_dic and "vip" not in color:
                    pushcolor_dic[color] -= self.vip_dic[self.tgt][color]

        for color in self.pushpunish:
            if color in pushcolor_dic and "vip" not in color:
                pushcolor_dic[color] -= self.pushpunish[color]

        for color in pushcolor_dic:
            if pushcolor_dic[color] > 0 and "vip" not in color:
                if color in self.pushpunish:
                    self.pushpunish[color] += 1
                else:
                    self.pushpunish[color] = 1
        return pushcolor_dic

    def stop(self):
        self.stop_now = True
        self.ws.close()
