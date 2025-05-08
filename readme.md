1.查找界面上是否有select_start.png
2.有的话进行点击，进入下一步, 没有的话重新进行查找
3.识别battle_start.png,
4.有的话进行点击，进入下一步, 没有的话重复查找3次，还是没找到回到第一步
5.点击下画面
6.查找界面上是否有battle_skip.png
7.有的话进行点击，没有的话重复查找3次后，还是没找到回到第一步
8.查找界面上是否有ok.png
9.有的话进行点击操作，没有的话重复查找3次，还是没找到的话回到第一步
10.点击下画面
11.查找界面上是否有click_continue.png
12.有的话进行点击，没有的话重复查找3次后，还是没找到回到第一步
13.查找界面上是否有click_continue.png
14.有的话进行点击，没有的话重复查找3次后，还是没找到回到第一步
15.查找界面上是否有click_continue.png
16.有的话进行点击，没有的话重复查找3次后，还是没找到回到第一步
17.我希望上述的步骤，可以有等待时间默认为1秒，针对不同的步骤可以额外控制等待时间
18.我还希望可以知道，当前正在进行的步骤是哪一步



import pyautogui
import time
import random
import json
import os
import logging
import win32gui
import win32con
import cv2
import numpy as np
from typing import Dict, Tuple, Optional, Any

def _setup_transparent_window(self):
        """窗口透明化处理"""
        try:
            hwnd = win32gui.WindowFromPoint(self.origin_pos["position"])
            self.game_hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
            win32gui.SetWindowLong(self.game_hwnd, win32con.GWL_EXSTYLE, win32con.WS_EX_LAYERED)
            win32gui.SetLayeredWindowAttributes(self.game_hwnd, 0, 180, win32con.LWA_ALPHA)
        except Exception as e:
            logging.exception("窗口透明化失败")