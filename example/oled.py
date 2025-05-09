from machine import SoftI2C, Pin, RTC
from ssd1306 import SSD1306_I2C
import time
import _thread

class OLED:
    def __init__(self, scl=6, sda=5, address=0x3C, width=72, height=40):
        """初始化OLED显示屏"""
        self.scl = scl
        self.sda = sda
        self.width = width
        self.height = height
        self.address = address
        
        self._init_i2c()
        self._init_oled()
        
        self.rtc = RTC()
        self.line_height = 10  # 每行高度（像素）
        self.padding_top = 5   # 顶部边距
        self.char_width = 8    # 每个字符的宽度（像素）
        
        # 滚动相关参数
        self.scroll_speed = 1       # 滚动速度（像素/帧）
        self.scroll_pause = 50      # 滚动前的暂停时间（帧）
        self.scroll_buffer = 8      # 超出屏幕的额外缓冲像素
        
        # 每行的滚动状态
        self.line_states = [
            {"position": 0, "pause": self.scroll_pause, "direction": 1} for _ in range(3)
        ]
        
        # 线程相关变量
        self._display_data = []
        self._update_interval = 0.05
        self._thread_running = False
        self._lock = _thread.allocate_lock()

    def _init_i2c(self):
        """初始化I2C接口"""
        self.i2c = SoftI2C(scl=Pin(self.scl), sda=Pin(self.sda), freq=400000)
        # 检查设备连接
        if self.address not in self.i2c.scan():
            print(f"错误: 未检测到I2C设备 {hex(self.address)}")

    def _init_oled(self):
        try:
            self.oled = SSD1306_I2C(self.width, self.height, self.i2c, addr=self.address)
        except Exception as e:
            print(f"OLED初始化失败: {e}")

    def _update_display_worker(self):
        """后台线程工作函数，处理显示更新"""
        while self._thread_running:
            try:
                with self._lock:
                    if self._display_data:
                        self._update_display_internal(self._display_data)
            except Exception as e:
                print(f"显示更新线程错误: {e}")
            time.sleep(self._update_interval)

    def _update_display_internal(self, lines):
        """内部显示更新方法，由线程调用"""
        self.oled.fill(0)
        
        try:
            # 确保有3行数据
            while len(lines) < 3:
                lines.append("")
                
            # 显示3行内容（支持滚动）
            for i, line in enumerate(lines):
                self._draw_line_with_scroll(i, line)
                
        except KeyboardInterrupt:
            print("检测到Ctrl+C中断，程序复位...")
            return
        except (ValueError, KeyError) as e:
            # 错误处理：显示错误信息
            self.oled.text("Error: " + str(e)[:8], 5, 15)
            
        self.oled.show()

    def _draw_line_with_scroll(self, line_index, text):
        """绘制单行文本，自动处理长文本滚动"""
        state = self.line_states[line_index]
        text_width = len(text) * self.char_width
        
        # 计算Y坐标
        y_pos = self.padding_top + line_index * self.line_height
        
        # 如果文本需要滚动
        if text_width > self.width:
            # 滚动逻辑
            if state["pause"] > 0:
                state["pause"] -= 1
            else:
                state["position"] += state["direction"] * self.scroll_speed
                
                # 到达右边界时重置到左边界
                if state["position"] >= text_width + self.scroll_buffer:
                    state["position"] = -self.width
                    
            # 绘制滚动文本
            self.oled.text(text, -state["position"], y_pos)
        else:
            # 短文本直接居中显示
            x_pos = max(0, (self.width - text_width) // 2)
            self.oled.text(text, x_pos, y_pos)

    def display_text(self, lines):
        """设置要显示的文本内容，由主线程调用"""
        with self._lock:
            self._display_data = lines.copy()

    def start_display_thread(self, update_interval=0.05):
        """启动显示更新线程"""
        if not self._thread_running:
            self._update_interval = update_interval
            self._thread_running = True
            _thread.start_new_thread(self._update_display_worker, ())
            print("OLED显示线程已启动")

    def stop_display_thread(self):
        """停止显示更新线程"""
        self._thread_running = False
        time.sleep(self._update_interval * 2)  # 等待线程退出
        print("OLED显示线程已停止")

    def scroll_text(self, lines):
        # 可在主循环中调用此函数
        for idx, line in enumerate(lines[:3]):
            state = self.line_states[idx]
            text_width = len(line) * self.char_width
            if text_width > self.width:
                if state["pause"] > 0:
                    state["pause"] -= 1
                else:
                    state["position"] -= self.scroll_speed
                    if abs(state["position"]) > (text_width - self.width + self.scroll_buffer):
                        state["pause"] = self.scroll_pause
                        state["position"] = 0  # 重置滚动
            else:
                state["position"] = 0  # 无需滚动

# 使用示例
if __name__ == "__main__":
    oled = OLED()
    oled.start_display_thread()  # 启动显示线程
    
    try:
        while True:
            # 获取当前时间（MicroPython兼容方式）
            rtc_time = oled.rtc.datetime()
            time_str = f"{rtc_time[4]:02d}:{rtc_time[5]:02d}:{rtc_time[6]:02d}"
            
            # 示例数据（包含长文本）
            display_data = [
                time_str,
                "IP: 192.168.1.100 - Connecting to network...",
                "System Status: Running smoothly - All systems nominal"
            ]
            
            # 更新显示内容（非阻塞调用）
            oled.display_text(display_data)
            
            # 主线程可以执行其他任务
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("检测到Ctrl+C，程序退出")
    finally:
        oled.stop_display_thread()  # 停止显示线程
