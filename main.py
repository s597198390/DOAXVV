import pyautogui
import time
import random
import json
import os
import logging
import cv2
import numpy as np
from typing import Dict, Tuple, Optional, Any
from functools import wraps

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ==================== 装饰器模块 ====================
class TimingController:
    """时间控制装饰器集合（修复参数传递问题）"""
    
    @classmethod
    def delay(cls, pre_delay: float = 0, post_delay: float = 0):
        """通用延迟装饰器（自动处理时间参数）"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 提取时间参数并移除
                actual_pre = kwargs.pop('pre_delay', pre_delay)
                actual_post = kwargs.pop('post_delay', post_delay)
                
                # 处理前置等待
                if actual_pre > 0:
                    logging.debug(f"[{func.__name__}] 前置等待 {actual_pre}s")
                    time.sleep(actual_pre)
                
                # 执行原始方法
                result = func(*args, **kwargs)
                
                # 处理后置等待
                if actual_post > 0:
                    logging.debug(f"[{func.__name__}] 后置等待 {actual_post}s")
                    time.sleep(actual_post)
                
                return result
            return wrapper
        return decorator

# ==================== 核心功能模块 ====================
class ImageFinder(TimingController):
    _IMAGE_CACHE: Dict[str, np.ndarray] = {}
    
    def __init__(self, config: Dict):
        self.config = config

    @TimingController.delay(pre_delay=0.5)
    def find_image(self, img_name: str) -> Optional[Tuple[int, int]]:
        """基础查找方法"""
        if img_name not in self._IMAGE_CACHE:
            img_path = os.path.join('images', img_name)
            if not os.path.exists(img_path):
                logging.error(f"图片不存在: {img_path}")
                return None
            try:
                self._IMAGE_CACHE[img_name] = cv2.cvtColor(cv2.imread(img_path), cv2.COLOR_BGR2GRAY)
            except Exception as e:
                logging.error(f"图片加载失败: {str(e)}")
                return None
        
        try:
            confidence = self.config['battle']['confidence_thresholds'].get(
                img_name, self.config['battle']['confidence_thresholds']['default']
            )
            location = pyautogui.locateCenterOnScreen(
                self._IMAGE_CACHE[img_name],
                confidence=confidence,
                grayscale=True
            )
            return (location.x, location.y) if location else None
        except Exception as e:
            logging.error(f"图像查找异常:{img_name} {str(e)}")
            return None

    @TimingController.delay(post_delay=1.0)
    def find_with_retry(self, img_name: str, max_attempts: int = 3, **kwargs) -> Optional[Tuple[int, int]]:
        """带重试的查找"""
        for attempt in range(1, max_attempts + 1):
            # 正确传递参数（自动过滤时间参数）
            if position := self.find_image(img_name):
                logging.info(f"第 {attempt} 次尝试成功找到 {img_name}")
                return position
            logging.debug(f"第 {attempt} 次查找 {img_name} 失败")
            time.sleep(self.config['battle'].get('retry_interval', 1))
        return None

class ClickExecutor(TimingController):
    def __init__(self, config: Dict):
        self.config = config
        self._CLICK_OFFSET = 5
        self._CLICK_DURATION_RANGE = (0.2, 0.5)

    @TimingController.delay(pre_delay=0.3, post_delay=0.5)
    def execute_click(self, 
                    position: Tuple[int, int], 
                    offset_x: int = 0,
                    offset_y: int = 0,
                    random_offset: bool = True) -> bool:
        """执行点击操作"""
        try:
            # 计算目标坐标
            target_x = position[0] + offset_x
            target_y = position[1] + offset_y

            # 添加随机偏移
            if random_offset:
                target_x += random.randint(-self._CLICK_OFFSET, self._CLICK_OFFSET)
                target_y += random.randint(-self._CLICK_OFFSET, self._CLICK_OFFSET)

            screen_w, screen_h = pyautogui.size()
            # 边界检查
            target_x = max(0, min(target_x, screen_w))
            target_y = max(0, min(target_y, screen_h))

            # 执行点击
            pyautogui.moveTo(target_x, target_y, duration=random.uniform(0.1, 0.3))
            pyautogui.click(duration=random.uniform(*self._CLICK_DURATION_RANGE))
            # logging.info(f"成功点击坐标: ({target_x}, {target_y})")
            return True
        except Exception as e:
            logging.error(f"点击操作失败: {str(e)}")
            return False

# ==================== 业务逻辑模块 ====================
class GameAuto:
    def __init__(self):
        self.cfg = self._load_config()
        self.finder = ImageFinder(self.cfg)
        self.clicker = ClickExecutor(self.cfg)
        self.origin_pos = None
        
        self._init_screen_info()
        self._find_origin_position()

    def _load_config(self) -> Dict:
        """加载配置文件"""
        default_cfg = {
            'battle': {
                'retry_interval': 2,
                'confidence_thresholds': {
                    'continue.png': 0.4,
                    'default': 0.8
                },
                'battle_duration': 120
            }
        }
        
        try:
            with open('config.json') as f:
                return self._deep_merge(default_cfg, json.load(f))
        except Exception as e:
            logging.warning(f"使用默认配置: {str(e)}")
            return default_cfg

    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """深度合并字典"""
        for key, val in update.items():
            if isinstance(val, dict):
                base[key] = self._deep_merge(base.get(key, {}), val)
            else:
                base[key] = val
        return base

    def _init_screen_info(self):
        """初始化屏幕信息"""
        try:
            self.screen_w, self.screen_h = pyautogui.size()
            logging.info(f"屏幕分辨率: {self.screen_w}x{self.screen_h}")
        except Exception as e:
            logging.error(f"屏幕信息获取失败: {str(e)}")
            raise

    def _find_origin_position(self):
        """定位初始坐标（带自定义时间控制）"""
        if position := self.finder.find_with_retry(
            'game_pos.png',
            pre_delay=1.0,  # 查找前等待
            post_delay=1.0   # 找到后等待
        ):
            self.origin_pos = position
            logging.info(f"初始坐标: {position}")
        else:
            raise RuntimeError("游戏初始坐标定位失败")

    def smart_click(self, 
                  img_name: str, 
                  offset_x: int = 0, 
                  offset_y: int = 0,
                  **kwargs) -> bool:
        """智能点击流程"""
        if position := self.finder.find_with_retry(img_name, **kwargs):
            return self.clicker.execute_click(
                position,
                offset_x,
                offset_y,
                **kwargs
            )
        return False

    def execute_battle_flow(self):
        """主战斗流程控制器"""
        logging.info("启动战斗循环")
        try:
            while True:
                self._battle_cycle()
        except KeyboardInterrupt:
            logging.info("用户中断操作")
        except Exception as e:
            logging.error(f"运行异常: {str(e)}")
            raise

    def _battle_cycle(self):
        """完整的战斗周期"""
        # 进入配队界面（带自定义时间参数）
        if self._process_phase('select_start.png', "配队界面", pre_delay=2.0):
            if self._process_battle_start():
                self._handle_battle_result()

    def _process_phase(self, img_name: str, phase_name: str, **kwargs) -> bool:
        """通用阶段处理器"""
        if self.smart_click(img_name, **kwargs):
            logging.info(f"进入 {phase_name}")
            return True
        logging.debug(f"未进入 {phase_name}")
        return False

    def _process_battle_start(self) -> bool:
        """战斗开始处理流程"""
        # 带时间参数的点击
        if not self.smart_click('battle_start.png', post_delay=2.0):
            return False

        # 处理疲劳值（带特殊重试参数）
        if fatigue_pos := self.finder.find_with_retry(
            'fatigue_value.png',
            max_attempts=2,
            pre_delay=0.5
        ):
            self.clicker.execute_click(fatigue_pos, offset_x=72, offset_y=55, pre_delay=1.0)
            self.smart_click('ok.png', pre_delay=1.0)
            return self.smart_click('battle_start.png', pre_delay=1.0,post_delay=2.0)
        return True

    def _handle_battle_result(self):
        """战斗结果处理"""
        logging.info("进入战斗流程")
        self.clicker.execute_click(self.origin_pos, 
                                 offset_x=200, 
                                 offset_y=200,
                                 pre_delay=2.5)
        # 重复点击一次防止之前没点击成功
        self.clicker.execute_click(self.origin_pos, 
                                 offset_x=200, 
                                 offset_y=200,
                                 pre_delay=2.5)

        if self.smart_click('battle_skip.png', post_delay=1.0):
            self._process_skip_battle()
        else:
            self._process_normal_battle()

    def _process_skip_battle(self):
        """跳过战斗处理"""
        self.smart_click('ok.png', pre_delay=1.0, post_delay=1.0)
        self.clicker.execute_click(self.origin_pos, 
                                      offset_x=160, 
                                      offset_y=100,
                                      pre_delay=1.5)
        self.smart_click('result.png', pre_delay=1.0)
        self.smart_click('result.png', pre_delay=1.0)
        self.smart_click('ok.png', pre_delay=1.0)
        self.smart_click('exrpensive.png', pre_delay=1.0)
        self.smart_click('exrpensive.png', pre_delay=1.0)
        # for _ in range(10):
        #     self.clicker.execute_click(self.origin_pos, 
        #                              offset_x=160, 
        #                              offset_y=100,
        #                              pre_delay=1.5)
        time.sleep(4)

    def _process_normal_battle(self):
        """正常战斗流程"""
        duration = self.cfg['battle'].get('battle_duration', 80)
        logging.info(f"进入正常战斗流程，预计持续时间: {duration}秒")
        time.sleep(duration)

if __name__ == "__main__":
    try:
        GameAuto().execute_battle_flow()
    except Exception as e:
        logging.error(f"程序异常终止: {str(e)}")