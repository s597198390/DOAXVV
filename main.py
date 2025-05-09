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
class ImageFinder():
    _IMAGE_CACHE: Dict[str, np.ndarray] = {}
    
    def __init__(self, config: Dict):
        self.config = config

    def _load_image(self, img_name: str) -> Optional[np.ndarray]:
        """封装图片加载逻辑"""
        if img_name in self._IMAGE_CACHE:
            return self._IMAGE_CACHE[img_name]
            
        img_path = os.path.join('images', img_name)
        if not os.path.exists(img_path):
            logging.error(f"图片路径不存在: {img_path}")
            self._IMAGE_CACHE[img_name] = None
            return None

        try:
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                raise ValueError("OpenCV无法解码图像")
            self._IMAGE_CACHE[img_name] = img
            return img
        except Exception as e:
            logging.error(f"图片加载失败 [{img_path}]: {str(e)}")
            self._IMAGE_CACHE[img_name] = None  # 缓存加载失败状态
            return None

    @TimingController.delay(pre_delay=0.5)
    def find_image(self, img_name: str) -> Optional[Tuple[int, int]]:
        """基础查找方法"""
        image = self._load_image(img_name)
        if image is None:
            return None  # 已记录错误，直接返回
           
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

    @TimingController.delay()
    def find_with_retry(self, 
                      img_name: str, 
                      max_attempts: int = 3,
                      base_interval: float = None,
                      **kwargs) -> Optional[Tuple[int, int]]:
        """优化重试机制：指数退避+随机扰动"""
        interval = base_interval or self.config['battle'].get('retry_interval', 1)
        
        for attempt in range(1, max_attempts + 1):
            if position := self.find_image(img_name):
                logging.info(f"成功找到 {img_name} (第{attempt}次)")
                return position
                
            # 指数退避算法：2^attempt * base + random
            sleep_time = (2 ** attempt) * interval + random.uniform(-0.2, 0.2)
            logging.debug(f"等待 {sleep_time:.2f}s 后重试")
            time.sleep(max(sleep_time, 0.1))  # 保证最小等待时间
            
        return None

class ClickExecutor():
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
        if self._process_phase('select_start.png', "配队界面", pre_delay=1.0):
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
                                 pre_delay=1.0)
        # 重复点击一次防止之前没点击成功
        self.clicker.execute_click(self.origin_pos, 
                                 offset_x=200, 
                                 offset_y=200,
                                 pre_delay=2.0)

        if self.smart_click('battle_skip.png', post_delay=1.0):
            self._process_skip_battle()
        else:
            self._process_normal_battle()

    def _process_skip_battle(self):
        """跳过战斗处理"""
        self.smart_click('ok.png', post_delay=1.0)
        self.clicker.execute_click(self.origin_pos, 
                                      offset_x=160, 
                                      offset_y=100,
                                      pre_delay=1.5)
        self.smart_click('result.png', pre_delay=1.0)
        if self.finder.find_with_retry('huodong.png', max_attempts=2, pre_delay=1.0):
            self.smart_click('ok.png', pre_delay=1.0, max_attempts=2)
        if self.finder.find_with_retry('level.png', max_attempts=2, pre_delay=1.0):
            self.smart_click('ok.png', pre_delay=1.0, max_attempts=2)
        self.smart_click('result.png', pre_delay=1.0)
        self.smart_click('expensive.png', pre_delay=1.5)
        # self.smart_click('expensive.png', pre_delay=1.5)
        self.smart_click('watch.png', max_attempts=2, pre_delay=1.0)
        time.sleep(3)
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