# -*- coding: UTF-8 -*-
"""
__Author__ = "WECENG"
__Version__ = "1.0.0"
__Description__ = "配置类"
__Created__ = 2023/10/27 09:54
"""
import json

# 各步骤间隔默认值（秒），可在 config.jsonc 的 delays 里覆盖
DEFAULT_DELAYS = {
    "poll": 0.2,       # 开售检测轮询间隔（秒）
    "refresh": 2.0,    # 页面强制刷新间隔（秒）
    "step": 0.5,       # 步骤间间隔：选场次/票价/观演人之间
    "click": 0.15,     # 连续点击间隔：如数量加号
    "scroll": 0.6,     # 滚动后等待
    "page_load": 2.5,  # 页面切换后等待（进选票页等）
}


class Config:
    def __init__(self, server_url, device_name, platform_version, keyword, users, city, date, session_index, price, price_index, if_commit_order, delays=None):
        self.server_url = server_url
        self.device_name = device_name
        self.platform_version = platform_version
        self.keyword = keyword
        self.users = users
        self.city = city
        self.date = date
        self.session_index = session_index
        self.price = price
        self.price_index = price_index
        self.if_commit_order = if_commit_order
        self.delays = dict(DEFAULT_DELAYS)
        if delays:
            self.delays.update({k: float(v) for k, v in delays.items() if v is not None})

    def delay(self, key):
        """读取某个间隔（秒）"""
        return self.delays.get(key, DEFAULT_DELAYS[key])

    @staticmethod
    def load_config():
        with open('config.jsonc', 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
        return Config(config['server_url'],
                      config.get('deviceName', 'emulator-5554'),
                      config.get('platformVersion', '16'),
                      config['keyword'],
                      config['users'],
                      config['city'],
                      config['date'],
                      config.get('session_index', 0),
                      config['price'],
                      config['price_index'],
                      config['if_commit_order'],
                      config.get('delays'))