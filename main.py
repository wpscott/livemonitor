from .monitors.Monitor import Monitor

from pathlib import Path
import json
import time

if __name__ == "__main__":
    logs = Path("./log")
    if not logs.exists():
        logs.mkdir()
    pausefile = Path("./pause.json")
    if not pausefile.exists():
        with open(pausefile, "w", encoding="utf-8") as f:
            f.write("[]")

    # 读取配置文件
    config_file = Path("./spider.json")
    config_name = input("默认为spider，不用输入json后缀名\n请输入配置文件名称：")
    while True:
        if not config_name:
            break
        config_file = Path(f"./{config_name}.json")
        if config_file.exists():
            break
        else:
            config_name = input("该配置文件不存在，请重新输入:")
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 启动并监视主监视器
    monitor = Monitor("主线程", "main", "main", config)
    monitor.Daemon = True
    monitor.start()
    while True:
        time.sleep(30)
        monitor.checksubmonitor()
