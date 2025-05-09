from machine import I2C, Pin, RTC
from ssd1306 import SSD1306_I2C
import time

# I2C设备地址
I2C_SCL = 6
I2C_SDA = 5
I2C_ADDR = 0x3C

class OLED:
    def __init__(self, scl_pin=I2C_SCL, sda_pin=I2C_SDA, oled_addr=I2C_ADDR, width=72, height=40):
        """初始化OLED显示屏"""
        self.i2c = I2C(0, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=400000)
        self.oled = SSD1306_I2C(width, height, self.i2c, addr=oled_addr)
        self.rtc = RTC()
        self.width = width
        self.height = height
        self.line_height = 10  # 每行高度（像素）
        self.padding_top = 5   # 顶部边距
        self.char_width = 8    # 每个字符的宽度（像素）
        
        # 检查设备连接
        if oled_addr not in self.i2c.scan():
            raise RuntimeError(f"OLED not found at address {hex(oled_addr)}")
            
        # 滚动相关参数
        self.scroll_speed = 1       # 滚动速度（像素/帧）
        self.scroll_pause = 50      # 滚动前的暂停时间（帧）
        self.scroll_buffer = 8      # 超出屏幕的额外缓冲像素
        
        # 每行的滚动状态
        self.line_states = [
            {"position": 0, "pause": self.scroll_pause, "direction": 1} for _ in range(3)
        ]

    def update_display(self, lines):
        """更新OLED显示内容，支持长文本滚动"""
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

# 使用示例
if __name__ == "__main__":
    oled = OLED()
    
    update_interval = 0.05  # 更新间隔（秒）
    
    """持续更新显示屏内容"""
    while True:
        # 获取当前时间（MicroPython兼容方式）
        rtc_time = oled.rtc.datetime()
        time_str = f"{rtc_time[4]:02d}:{rtc_time[5]:02d}:{rtc_time[6]:02d}"
        
        # 示例数据（包含长文本）
        display_data = [
            time_str,
            "IP: 192.168.1.100 - Connecting to network...",  # 长文本会自动滚动
            "System Status: Running smoothly - All systems nominal"  # 长文本会自动滚动
        ]
        
        oled.update_display(display_data)
        time.sleep(update_interval)
