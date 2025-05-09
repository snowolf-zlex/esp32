from machine import I2C, Pin
import math
import time

# I2C设备地址
I2C_SCL = 9
I2C_SDA = 8

class PCA9685:
    """
    PCA9685 PWM控制器驱动
    """
    MODE1 = 0x00
    MODE2 = 0x01
    SUBADR1 = 0x02
    SUBADR2 = 0x03
    SUBADR3 = 0x04
    PRESCALE = 0xFE
    
    # 通道控制寄存器地址
    CHANNEL_ON_L = 0x06
    CHANNEL_ON_H = 0x07
    CHANNEL_OFF_L = 0x08
    CHANNEL_OFF_H = 0x09
    ALL_CHANNEL_ON_L = 0xFA
    ALL_CHANNEL_ON_H = 0xFB
    ALL_CHANNEL_OFF_L = 0xFC
    ALL_CHANNEL_OFF_H = 0xFD

    # 模式寄存器值
    RESTART = 0x80
    SLEEP = 0x10
    ALLCALL = 0x01
    INVRT = 0x10
    OUTDRV = 0x04

    def __init__(self, scl=I2C_SCL, sda=I2C_SDA, max_channel=16, calibrate_angle=90):
        self.address = 0x40
        self.scl = scl
        self.sda = sda
        self._init_i2c()
        self._reset()
        self._set_pwm_freq(50)  # 50Hz适合9g舵机
        
        # 舵机控制参数
        self.max_channel = max_channel
        self.calibrate_angle = calibrate_angle
        self.servo_targets = [self.calibrate_angle] * self.max_channel  # 存储每个舵机的目标角度，初始值为90度
        self.servo_current = [self.calibrate_angle] * self.max_channel  # 记录每个舵机的当前角度，初始值为90度
        self.servo_speeds = [self.calibrate_angle] * self.max_channel  # 每个舵机的移动速度，单位为度/秒，初始值为90度/秒
        self.last_update = time.ticks_ms()
        self.calibrate_all_servos()

    def _init_i2c(self):
        """初始化I2C接口"""
        self.i2c = I2C(0, scl=Pin(self.scl), sda=Pin(self.sda), freq=400000)
        if self.address not in self.i2c.scan():
            print(f"错误: 未检测到I2C设备 0x{self.address:02X}")

    def _write(self, reg, value):
        """写入寄存器"""
        self.i2c.writeto_mem(self.address, reg, bytes([value]))

    def _read(self, reg):
        """读取寄存器"""
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]

    def _reset(self):
        """重置设备"""
        self._write(self.MODE1, 0x00)

    def _set_pwm_freq(self, freq_hz):
        """设置PWM频率"""
        prescale = int(round(25000000 / (4096 * freq_hz))) - 1
        old_mode = self._read(self.MODE1)
        self._write(self.MODE1, (old_mode & 0x7F) | 0x10)  # 睡眠模式
        self._write(self.PRESCALE, prescale)
        self._write(self.MODE1, old_mode)
        time.sleep_ms(5)
        self._write(self.MODE1, old_mode | 0x80)  # 重启

    def _set_servo_angle(self, channel, angle):
        """设置舵机角度(立即生效)"""
        angle = max(0, min(180, angle))
        pulse = 500 + (angle / 180) * 2000  # 500-2500μs
        pwm = int(4096 * pulse / 20000)     # 转换为12bit值
        self._write(self.CHANNEL_ON_L + 4*channel, 0)
        self._write(self.CHANNEL_OFF_L + 4*channel, pwm & 0xFF)
        self._write(self.CHANNEL_OFF_L + 4*channel + 1, pwm >> 8)

    def calibrate_all_servos(self, angle=90):
        """校准所有舵机到指定角度"""
        for ch in range(self.max_channel):
            self._set_servo_angle(ch, angle)
            time.sleep_ms(20)

    def _update_servos(self):
        """手动调用更新舵机位置(应在主循环中定期调用)"""
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self.last_update) / 1000  # 转换为秒
        if elapsed >= 0.02:  # 约50Hz更新频率
            self.last_update = now
            for ch in range(self.max_channel):
                target = self.servo_targets[ch]
                current = self.servo_current[ch]
                if abs(target - current) > 1.0:  # 需要移动
                    step = self.servo_speeds[ch] * elapsed
                    new_angle = current + step if target > current else current - step
                    new_angle = max(0, min(180, new_angle))
                    self.servo_current[ch] = new_angle
                    self._set_servo_angle(ch, new_angle)

    def move(self, angles, speeds=None):
        """设置所有舵机目标角度并平滑移动
        参数:
            angles: 包含16个舵机目标角度的列表，每个角度范围为0到180度。
            speeds: 包含16个舵机移动速度的列表，单位为度/秒。
                      如果为None，则使用每个舵机的当前速度值；
                      如果提供了该参数且长度与舵机数量相同，
                      则使用传入的速度值更新每个舵机的速度。
        """
        # 设置目标角度和速度
        for ch in range(self.max_channel):
            self.servo_targets[ch] = max(0, min(180, angles[ch]))
            if speeds and len(speeds) == self.max_channel:
                self.servo_speeds[ch] = speeds[ch]
        
        # 持续更新直到所有舵机接近目标位置
        while True:
            self._update_servos()
            all_ready = all(
                abs(self.servo_targets[ch] - self.servo_current[ch]) <= 1.0
                for ch in range(self.max_channel)
            )
            if all_ready:
                break
            time.sleep_ms(20)

# 使用示例
def wave_demo():
    """波浪效果演示"""
    print("开始波浪摆动...")
    pca = PCA9685()
    start_time = time.time()
    try:
        while time.time() - start_time < 10:  # 运行10秒
            # 生成波浪角度(相位偏移)
            base = (time.time() - start_time) * 2  # 2弧度/秒
            angles = [math.sin(base + n*0.4)*45 + 90 for n in range(16)]
            # 更新目标角度并移动
            pca.move(angles)
    except KeyboardInterrupt:
        print("检测到Ctrl+C中断，将舵机恢复到中间位置...")  
    finally:
        # 测试结束后将所有舵机回到中间位置
        print("测试完成，将舵机恢复到中间位置...")
        pca.calibrate_all_servos()


def test_random_angles(iterations=10,  delay=1.0):
    """
    测试方法：随机生成16个角度并控制所有舵机转动
    
    参数:
        iterations: 测试迭代次数
        delay: 每次转动后的延迟时间(秒)
    """
    import random
    print("开始随机角度测试...")
    pca = PCA9685()
    
    try:
        for i in range(iterations):
            print(f"测试迭代 {i+1}/{iterations}")
            
            # 生成16个随机角度
            random_angles = [random.randint(0, 180) for _ in range(16)]
            
            # 设置所有舵机目标角度和速度
            pca.move(random_angles)
            
            # 打印当前角度
            print(f"当前角度: {[round(angle) for angle in pca.servo_current]}")
    except KeyboardInterrupt:
        print("检测到Ctrl+C中断，将舵机恢复到中间位置...")        
    finally:
        # 测试结束后将所有舵机回到中间位置
        print("测试完成，将舵机恢复到中间位置...")
        pca.calibrate_all_servos()

if __name__ == "__main__":
    wave_demo()
    test_random_angles(iterations=15)
