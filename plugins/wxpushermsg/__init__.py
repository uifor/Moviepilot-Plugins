# -*- coding: utf-8 -*-
import requests
import json
import logging
import threading
from typing import Any, List, Dict, Tuple

from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.utils.http import RequestUtils

lock = threading.Lock()


class WxPusherMsg(_PluginBase):
    # 插件名称
    plugin_name = "WxPusher消息通知"
    # 插件描述
    plugin_desc = "支持使用WxPusher发送消息通知。"
    # 插件图标 (请替换为你的插件图标 URL)
    plugin_icon = "https://raw.githubusercontent.com/uifor/MoviePilot-Plugins/main/icons/wxpusher.jpg"
    # 插件版本
    plugin_version = "1.2"
    # 插件作者
    plugin_author = "uifor"
    # 作者主页 (请替换为你的 GitHub 链接)
    author_url = "https://github.com/uifor"
    # 插件配置项ID前缀
    plugin_config_prefix = "wxpushermsg_"
    # 加载顺序
    plugin_order = 32  # 确保加载顺序在 ServerChanMsg 之后或之前
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _onlyonce = False
    _uuid = None
    _apptoken = None
    _msgtypes = []

    _scheduler = None
    _event = threading.Event()

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._uuid = config.get("uuid")
            self._apptoken = config.get("apptoken")
            self._msgtypes = config.get("msgtypes") or []

        if self._onlyonce:
            flag = self.send_msg(title="WxPusher消息通知测试",
                                 text="WxPusher消息通知测试成功！")
            if flag:
                self.systemmessage.put("WxPusher消息通知测试成功！")
            self._onlyonce = False

        self.__update_config()

    def __update_config(self):
        """
        更新配置
        :return:
        """
        config = {
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "uuid": self._uuid,
            "apptoken": self._apptoken,
            "msgtypes": self._msgtypes,
        }
        self.update_config(config)

    def get_state(self) -> bool:
        return self._enabled and (True if (self._uuid and self._apptoken) else False)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        # 编历 NotificationType 枚举，生成消息类型选项
        MsgTypeOptions = []
        for item in NotificationType:
            MsgTypeOptions.append({
                "title": item.value,
                "value": item.name
            })
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6,
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                            'hint': '开启后插件将处于激活状态',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6,
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立刻发送测试',
                                            'hint': '一次性任务，运行后自动关闭',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'uuid',
                                            'label': 'WxPusher 用户 UUID',
                                            'placeholder': '你的 WxPusher 用户 UUID',
                                            'hint': '必填；你的 WxPusher 用户 UUID。',
                                            'persistent-hint': True,
                                            'clearable': True,
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'apptoken',
                                            'label': 'WxPusher 应用 AppToken',
                                            'placeholder': '你的 WxPusher 应用 AppToken',
                                            'hint': '必填；你的 WxPusher 应用 AppToken。',
                                            'persistent-hint': True,
                                            'clearable': True,
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': True,
                                            'chips': True,
                                            'model': 'msgtypes',
                                            'label': '消息类型',
                                            'items': MsgTypeOptions,
                                            'clearable': True,
                                            'hint': '自定义需要接受并发送的消息类型',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                ]
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "uuid": "",
            "apptoken": "",
            'msgtypes': [],
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType.NoticeMessage)
    def send(self, event: Event):
        """
        消息发送事件
        """
        if not self.get_state():
            return

        if not event.event_data:
            return

        msg_body = event.event_data
        # 渠道
        channel = msg_body.get("channel")
        if channel:
            return
        # 类型
        msg_type: NotificationType = msg_body.get("type")
        # 标题
        title = msg_body.get("title")
        # 文本
        text = msg_body.get("text")
        # 图片
        image = msg_body.get("image") # 未使用，但保留

        if not title and not text:
            logger.warn("标题和内容不能同时为空")
            return

        if (msg_type and self._msgtypes
                and msg_type.name not in self._msgtypes):
            logger.info(f"消息类型 {msg_type.value} 未开启消息发送")
            return

        self.send_msg(title=title, text=text) # 移除 image 参数

    def send_msg(self, title, text):
        """
        发送消息
        """
        with lock:
            try:
                if not self._uuid or not self._apptoken:
                    raise Exception("请配置 WxPusher 的 UUID 和 AppToken。")

                url = "https://wxpusher.zjiecode.com/api/send/message"
                data = {
                    "appToken": self._apptoken,
                    "content": text,
                    "summary": title,
                    "contentType": 1,  # 默认为文本消息
                    "uids": [self._uuid],
                }
                headers = {'Content-Type': 'application/json'}

                res = RequestUtils().post_res(url=url, data=json.dumps(data), headers=headers)

                if res:
                    ret_json = res.json()
                    code = ret_json.get('code')
                    msg = ret_json.get('msg')
                    if code == 1000:
                        logger.info("WxPusher 消息发送成功")
                    else:
                        raise Exception(f"WxPusher 消息发送失败：{msg}")
                elif res is not None:
                    raise Exception(f"WxPusher消息发送失败，错误码：{res.status_code}，错误原因：{res.reason}")
                else:
                    raise Exception(f"WxPusher消息发送失败：未获取到返回信息")
                return True
            except Exception as msg_e:
                logger.error(f"WxPusher 消息发送失败 - {str(msg_e)}")
                return False

    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._event.set()
                    self._scheduler.shutdown(wait=False)
                    self._event.clear()
                self._scheduler = None
        except Exception as e:
            logger.error(str(e))
