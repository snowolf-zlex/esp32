
import network
import ujson
import time
from machine import RTC

class WiFi:
    """WiFi连接管理类（单例模式）"""
    
    CONFIG_SSID = "ssid"
    CONFIG_PASSWORD = "password"
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, ap_ssid="ESP32", ap_ip="192.168.4.1", ap_password="12345678", config_file="wifi_config.json"):
        if self._initialized:
            return
            
        self.ap_ssid = ap_ssid
        self.ap_ip = ap_ip
        self.ap_password = ap_password
        self.config_file = config_file
        self.sta_if = network.WLAN(network.STA_IF)
        self.ap_if = network.WLAN(network.AP_IF)
        self.rtc = RTC()
        self._initialized = True

    def sync_time(self, ntp_server="pool.ntp.org"):
        """通过NTP同步时间"""
        try:
            import ntptime
            ntptime.host = ntp_server
            ntptime.settime()
            return True
        except Exception:
            return False

    def _read_wifi_config(self):
        """读取WiFi配置文件"""
        try:
            with open(self.config_file, "r") as f:
                return ujson.load(f)
        except (OSError, ValueError):
            return None
            
    def save_wifi_config(self, ssid, password):
        """保存WiFi配置到文件"""
        try:
            with open(self.config_file, "w") as f:
                ujson.dump({self.CONFIG_SSID: ssid, self.CONFIG_PASSWORD: password}, f)
            return True
        except OSError:
            return False
            
    def connect(self, ssid=None, password=None):
        """连接到WiFi网络"""
        if ssid and password:
            return self._connect(ssid, password)
            
        config = self._read_wifi_config()
        if config:
            return self._connect(config[self.CONFIG_SSID], config[self.CONFIG_PASSWORD])
            
        return False
            
    def _connect(self, ssid, password):
        """实际执行WiFi连接"""
        if self.sta_if.isconnected():
            return True
            
        self.sta_if.active(True)
        self.sta_if.connect(ssid, password)
        
        for _ in range(10):
            if self.sta_if.isconnected():
                return True
            time.sleep(1)
            
        return False
    
    def _format_date(self):
        """格式化日期为字符串：YYYY-MM-DD"""
        tm = self.rtc.datetime()
        return f"{tm[0]:04d}-{tm[1]:02d}-{tm[2]:02d}"

    def _format_time(self):
        """格式化时间为字符串：HH:MM:SS"""
        tm = self.rtc.datetime()
        return f"{tm[4]:02d}:{tm[5]:02d}:{tm[6]:02d}"

    def start_ap(self):
        """启动Access Point模式"""
        self.ap_if.active(True)
        self.ap_if.config(essid=self.ap_ssid, password=self.ap_password, authmode=network.AUTH_WPA_WPA2_PSK)
        self.ap_if.ifconfig(('192.168.10.1', '255.255.255.0', '192.168.10.1', '192.168.10.1'))
        return self.ap_if.active()

    def is_connected(self):
        """检查是否已连接到WiFi网络"""
        return self.sta_if.isconnected()
        
    def get_ip(self):
        """获取当前IP地址"""
        return self.sta_if.ifconfig()[0] if self.is_connected() else None
    
    def is_ap_active(self):
        """判断AP模式是否激活"""
        return self.ap_if.active()
    
    def get_ap_info(self):
        return self.ap_ssid , self.ap_if.ifconfig()[0]
    
    def is_ap_mode(self):
        """判断当前是否处于AP模式
        
        Returns:
            bool: 如果AP模式已激活且客户端可以连接返回True，否则返回False
        """
        return self.ap_if.active() and not self.sta_if.isconnected()
    
    def initialize(self):
        """初始化WiFi连接，优先使用保存的配置连接，失败则启动AP模式"""
        if self.is_connected():
            return self.sta_if
            
        if self.connect():
            return self.sta_if
            
        self.start_ap()
        return None    

    def get_current_ip(self):
        """获取当前连接的IP地址
        
        Returns:
            str: IP地址
                WiFi IP 或 AP IP
        """
        if self.is_connected():
            return self.sta_if.ifconfig()[0]
        elif self.ap_if.active():
            return self.ap_if.ifconfig()[0]
        return None

# 测试WiFi类功能的脚本
import time 

def test_wifi():
    # 创建WiFi实例
    wifi = WiFi()
    
    print("\n=== WiFi测试开始 ===")
    
    # 测试初始化连接
    print("\n测试WiFi初始化连接...")
    result = wifi.initialize()
    
    if result:
        print(f"已连接到WiFi，IP地址: {wifi.get_current_ip()}")
        
        # 只有在WiFi连接成功时才测试时间
        print("\n=== 时间测试开始 ===")
        
        # 显示当前时间（同步前）
        print(f"同步前的本地时间: {wifi._format_date()} {wifi._format_time()}")
        
        # 手动设置时间（可选）
        # self.set_manual_time(2025, 5, 8, 12, 0, 0)
        # print(f"手动设置后的时间: {self._format_date()} {self._format_time()}")
        
        # 同步时间
        print("尝试通过NTP同步时间...")
        if wifi.sync_time():
            print(f"同步后的本地时间: {wifi._format_date()} {wifi._format_time()}")
            
            # 测试时间格式
            print("\n测试时间格式:")
            print(f"日期: {wifi._format_date()}")
            print(f"时间: {wifi._format_time()}")
        else:
            print("时间同步失败，使用本地时间")
        
        print("\n=== 时间测试完成 ===")
        
    elif wifi.ap_if:
        ssid, ip = wifi.get_ap_info()
        print(f"已启动AP模式，SSID: {ssid}, IP: {ip}")
        print("由于未连接到WiFi，跳过时间同步测试")
    else:
        print("WiFi初始化失败")
    
    # 测试保存配置
    print("\n测试保存WiFi配置...")
    if wifi.save_wifi_config("ssid", "pawwsord"):
        print("配置保存成功")
    else:
        print("配置保存失败")
    
    # 测试读取配置
    print("\n测试读取WiFi配置...")
    config = wifi._read_wifi_config()
    if config:
        print(f"读取配置成功: SSID={config.get('ssid')}, Password={config.get('password')}")
    else:
        print("读取配置失败")
    
    # 测试连接状态
    print("\n测试连接状态...")
    print(f"是否已连接: {wifi.is_connected()}")
    print(f"是否处于AP模式: {wifi.is_ap_mode()}")
    
    # 测试获取IP
    print("\n测试获取IP地址...")
    current_ip = wifi.get_current_ip()
    print(f"当前IP地址: {current_ip if current_ip else '未连接'}")
    
    print("\n=== WiFi测试完成 ===")

if __name__ == "__main__":
    test_wifi()

