from machine import SoftI2C, Pin
import math
import time
import _thread

class PCA9685:
    """
    PCA9685 PWM控制器驱动 - 改进的异步舵机控制
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

    def __init__(self, scl=9, sda=8, address=0x40, max_channel=16, calibrate_angle=90):
        try:
            self.address = address
            self.scl = scl
            self.sda = sda
            self._init_i2c()
            self._reset()
            self._set_pwm_freq(50)  # 50Hz适合9g舵机
        
            # 舵机控制参数
            self.max_channel = max_channel
            self.calibrate_angle = calibrate_angle
            self.servo_targets = [self.calibrate_angle] * self.max_channel  # 存储每个舵机的目标角度
            self.servo_current = [self.calibrate_angle] * self.max_channel  # 记录每个舵机的当前角度
            self.servo_speeds = [self.calibrate_angle] * self.max_channel  # 每个舵机的移动速度(度/秒)
            self.last_update = time.ticks_ms()
            self.calibrate_all_servos()
            
            # 线程相关变量
            self._lock = _thread.allocate_lock()
            self._control_thread_running = False
            self._update_interval = 0.02  # 20ms更新间隔，约50Hz
            self._move_complete = True

        except Exception as e:
            print(f"PCA9685初始化失败: {e}")
            raise  # 重新抛出异常以便上层处理
        
    def _init_i2c(self):
        """初始化I2C接口"""
        self.i2c = SoftI2C(scl=Pin(self.scl), sda=Pin(self.sda), freq=400000)
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
        """更新舵机位置(在主循环中定期调用)"""
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self.last_update) / 1000  # 转换为秒
        if elapsed >= self._update_interval:  # 检查是否达到更新间隔
            self.last_update = now
            with self._lock:
                moving = False
                for ch in range(self.max_channel):
                    target = self.servo_targets[ch]
                    current = self.servo_current[ch]
                    if abs(target - current) > 1.0:  # 需要移动
                        step = self.servo_speeds[ch] * elapsed
                        new_angle = current + step if target > current else current - step
                        new_angle = max(0, min(180, new_angle))
                        self.servo_current[ch] = new_angle
                        self._set_servo_angle(ch, new_angle)
                        moving = True
                self._move_complete = not moving

    def _control_thread_worker(self):
        """舵机控制线程工作函数"""
        print("舵机控制线程已启动")
        while self._control_thread_running:
            self._update_servos()
            time.sleep_ms(int(self._update_interval * 1000))  # 等待下一个更新周期
        print("舵机控制线程已停止")

    def start_control_thread(self, update_interval=0.02):
        """启动舵机控制线程"""
        if not self._control_thread_running:
            self._update_interval = update_interval
            self._control_thread_running = True
            _thread.start_new_thread(self._control_thread_worker, ())
            print(f"舵机控制线程已启动，更新间隔: {update_interval*1000:.1f}ms")

    def stop_control_thread(self):
        """停止舵机控制线程"""
        if self._control_thread_running:
            self._control_thread_running = False
            time.sleep(int(self._update_interval * 1000 * 2))  # 等待线程退出
            print("舵机控制线程已停止")

    def move(self, angles, speeds=None):
        """设置所有舵机目标角度并平滑移动
        参数:
            angles: 包含16个舵机目标角度的列表，每个角度范围为0到180度。
            speeds: 包含16个舵机移动速度的列表，单位为度/秒。
        """
        if not self._control_thread_running:
            print("警告: 控制线程未运行，将先启动线程")
            self.start_control_thread()
            
        with self._lock:
            # 设置目标角度和速度
            for ch in range(self.max_channel):
                self.servo_targets[ch] = max(0, min(180, angles[ch]))
                if speeds and len(speeds) == self.max_channel:
                    self.servo_speeds[ch] = speeds[ch]
            self._move_complete = False
        #self.wait_for_move()    
    
    def is_moving(self):
        """检查是否有舵机正在移动"""
        with self._lock:
            return not self._move_complete
    
    def wait_for_move(self):
        """等待当前移动完成"""
        while self.is_moving():
            time.sleep_ms(50)
    
    def close(self):
        """释放资源并停止控制线程"""
        self.stop_control_thread()
        self.calibrate_all_servos()  # 回到中间位置

def main():
    import random
    servo = PCA9685()
    
    # 启动控制线程
    #servo.start_control_thread()
    
    iterations = 50
    try:    
        for i in range(iterations):

            # 生成随机角度
            random_angles = [random.randint(0, 180) for _ in range(16)]
            
            print(f"舵机移动, 第{i}轮, 角度: {random_angles}")

            # 启动舵机移动
            servo.move(random_angles)


    except KeyboardInterrupt:
        print("检测到Ctrl+C中断，将舵机恢复到中间位置...")
        return
    finally:
        # 测试结束后释放资源
        print("测试完成，将舵机恢复到中间位置...")
        servo.close()

if __name__ == "__main__":
    main()
