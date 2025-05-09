import network
import ujson
import time
from machine import RTC 

class WiFi:
    
    CONFIG_SSID = "ssid"
    CONFIG_PASSWORD = "password"
    
    """WiFi连接管理类（单例模式）"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super(WiFi, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, ap_ssid="ESP32", ap_ip="192.168.4.1", ap_password="12345678", config_file="wifi_config.json"):
        """初始化WiFi管理器"""
        if self._initialized:
            return
             
        self.ap_ssid = ap_ssid
        self.ap_ip = ap_ip
        self.ap_password = ap_password
        self.wifi_config_file = config_file
        self.sta_if = network.WLAN(network.STA_IF)
        self.ap_if = network.WLAN(network.AP_IF)
        self._initialized = True
        
        self.rtc = RTC()
        self.sync_time()

    def sync_time(self, ntp_server="pool.ntp.org"):
        """通过NTP同步时间"""
        try:
            import ntptime  # 按需导入ntptime
            ntptime.host = ntp_server
            ntptime.settime()
            print(f"Time synced from {ntp_server}")
            return True
        except Exception as e:
            print("NTP sync failed:", e)
            return False

    def set_manual_time(self, year, month, day, hour, minute, second):
        """手动设置时间"""
        self.rtc.datetime((year, month, day, 0, hour, minute, second, 0))

    def _format_time(self):
        """格式化时间字符串"""
        t = self.rtc.datetime()
        return f"{t[4]:02d}:{t[5]:02d}:{t[6]:02d}"

    def _format_date(self):
        """格式化日期字符串"""
        t = self.rtc.datetime()
        return f"{t[0]-2000:02d}-{t[1]:02d}-{t[2]:02d}"
    
    def _read_wifi_config(self):
        """读取WiFi配置文件"""
        try:
            with open(self.wifi_config_file, "r") as f:
                return ujson.load(f)
        except (OSError, ValueError):
            print(f"未能读取WiFi配置文件")
            return None
            
    def save_wifi_config(self, ssid, password):
        """保存WiFi配置到文件"""
        
        config = {
            self.CONFIG_SSID: ssid,
            self.CONFIG_PASSWORD: password
        }
        
        try:
            with open(self.wifi_config_file, "w") as f:
                ujson.dump(config, f)
                print(f"已保存WiFi配置文件 {self.wifi_config_file}")
            return True
        except OSError:
            print(f"未能保存WiFi配置文件")
            return False
            
    def _connect(self, ssid, password):
        """连接到指定的WiFi网络"""
        print(f"尝试连接WiFi: {ssid}")
        if not self.sta_if.isconnected():
            self.sta_if.active(True)
            self.ap_ssid = ssid
            self.ap_password = password
            self.sta_if.connect(ssid, password)
            
            timeout = 10
            while timeout > 0:
                if self.sta_if.isconnected():
                    print(f"WiFi连接成功:{ssid}")
                    print(f"网络配置:{self.sta_if.ifconfig()}")
                    print(f"主机名称:{self.sta_if.config('dhcp_hostname')}")
                    return True
                time.sleep(1)
                timeout -= 1
                
            print("WiFi连接超时")
        else:
            print(f"WiFi连接成功:{ssid}")
            print(f"网络配置:{self.sta_if.ifconfig()}")
            print(f"主机名称:{self.sta_if.config('dhcp_hostname')}")
            return True
            
        return False   

    def _start_ap_mode(self):
        """启动Access Point模式并设置自定义网络配置"""
        self.ap_if.active(True)
        
        # 设置AP参数
        self.ap_if.config(
            essid=self.ap_ssid,
            password=self.ap_password,
            authmode=network.AUTH_WPA_WPA2_PSK  # 认证模式
        )
        
        # 设置自定义网络配置 (IP, 子网掩码, 网关, DNS)
        self.ap_if.ifconfig(('192.168.10.1', '255.255.255.0', '192.168.10.1', '192.168.10.1'))
        
        # 等待AP激活
        while not self.ap_if.active():
            time.sleep(0.1)
        
        print(f"AP模式已启动: {self.ap_ssid}")
        print(f"AP IP: {self.ap_if.ifconfig()[0]}")
        print(f"AP Clients: {self.ap_if.status('stations')}")
        
        return self.ap_if

    def is_connected(self):
        """检查是否已连接到WiFi网络
        
        Returns:
            bool: 已连接返回True，未连接返回False
        """
        return self.sta_if.isconnected()
        
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
    
    def get_ap_info(self):
        return self.ap_ssid , self.ap_if.ifconfig()[0]
    
    def is_ap_mode(self):
        """判断当前是否处于AP模式
        
        Returns:
            bool: 如果AP模式已激活且客户端可以连接返回True，否则返回False
        """
        return self.ap_if.active() and not self.sta_if.isconnected()
    
    def initialize(self):
        """初始化WiFi连接"""
        
        if self.is_connected():
            return self.sta_if, None
        
        config = self._read_wifi_config()
        
        if config:
            if self._connect(config[self.CONFIG_SSID], config[self.CONFIG_PASSWORD]):
                return self.sta_if, None
            else:
                return None, self._start_ap_mode()
        else:
            return None, self._start_ap_mode()
    
    def test_time(self):
        """测试时间同步和格式化功能"""
        print("\n=== 时间测试开始 ===")
        
        # 显示当前时间（同步前）
        print(f"同步前的本地时间: {self._format_date()} {self._format_time()}")
        
        # 手动设置时间（可选）
        # self.set_manual_time(2025, 5, 8, 12, 0, 0)
        # print(f"手动设置后的时间: {self._format_date()} {self._format_time()}")
        
        # 同步时间
        print("尝试通过NTP同步时间...")
        if self.sync_time():
            print(f"同步后的本地时间: {self._format_date()} {self._format_time()}")
            
            # 测试时间格式
            print("\n测试时间格式:")
            print(f"日期: {self._format_date()}")
            print(f"时间: {self._format_time()}")
        else:
            print("时间同步失败，使用本地时间")
        
        print("\n=== 时间测试完成 ===")
        
        
# 测试WiFi类功能的脚本
import time 

def test_wifi():
    # 创建WiFi实例
    wifi = WiFi(ap_ssid="ESP32_TEST", ap_password="test1234")
    
    print("\n=== WiFi测试开始 ===")
    
    # 测试初始化连接
    print("\n测试WiFi初始化连接...")
    sta_if, ap_if = wifi.initialize()
    
    if sta_if:
        print(f"已连接到WiFi，IP地址: {wifi.get_current_ip()}")
        
        # 只有在WiFi连接成功时才测试时间
        wifi.test_time()
    elif ap_if:
        ssid, ip = wifi.get_ap_info()
        print(f"已启动AP模式，SSID: {ssid}, IP: {ip}")
        print("由于未连接到WiFi，跳过时间同步测试")
    else:
        print("WiFi初始化失败")
    
    # 测试保存配置
    print("\n测试保存WiFi配置...")
    if wifi.save_wifi_config("ssid", "password"):
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
