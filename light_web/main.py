import socket
import time
import _thread
import machine
import machine
import time
import _thread

class LED:
    def __init__(self, brightness=50):
        # LED引脚
        self.LED_PIN = 4
        # 初始化LED引脚为PWM模式，频率1000Hz
        self.led = machine.PWM(machine.Pin(self.LED_PIN), freq=1000, duty=0)
        # 全局变量用于控制闪烁线程
        self.stop_flag = False
        # 当前亮度值 (0-100)
        self.current_brightness = brightness

    # 设置LED亮度 (0-100%)
    def set_brightness(self, brightness):
        # 确保亮度在有效范围内
        brightness = max(0, min(100, brightness))
        # 将百分比转换为PWM占空比值 (0-1023)
        duty_cycle = int((brightness / 100) * 1023)
        self.led.duty(duty_cycle)
        self.current_brightness = brightness

    # 控制LED亮灭
    def on(self):
        self.set_brightness(100)
        
    def off(self):
        self.set_brightness(0)

    # 控制LED闪烁
    def blink(self, interval=0.5, brightness=100):
        self.stop_flag = False
    
        def blink_thread():
            while not self.stop_flag:
                self.set_brightness(brightness)
                time.sleep(interval)
                self.off()
                time.sleep(interval)
    
        _thread.start_new_thread(blink_thread, ())

    # 呼吸灯效果
    def breathe(self, duration=2, max_brightness=100):
        """
        实现LED呼吸灯效果
        
        参数:
            duration: 一个完整呼吸周期的时间(秒)
            max_brightness: 呼吸灯最大亮度(0-100)
        """
        self.stop_flag = False
        # 呼吸灯渐变的步数
        steps = 50
        # 每步的延迟时间
        delay = duration / steps / 2
    
        def breathe_thread():
            while not self.stop_flag:
                # 渐亮过程
                for i in range(steps + 1):
                    if self.stop_flag:
                        break
                    # 计算当前亮度
                    brightness = int((i / steps) * max_brightness)
                    self.set_brightness(brightness)
                    time.sleep(delay)
                
                # 渐灭过程
                for i in range(steps, -1, -1):
                    if self.stop_flag:
                        break
                    brightness = int((i / steps) * max_brightness)
                    self.set_brightness(brightness)
                    time.sleep(delay)
    
        _thread.start_new_thread(breathe_thread, ())

    # 停止所有闪烁和呼吸灯效果
    def stop(self):
        self.stop_flag = True
        time.sleep(0.1)  # 等待线程停止
        # 保持当前亮度，不强制关闭LED
        self.off()


# HTTP请求解析类
class HTTPRequest:
    def __init__(self, request_data):
        self.method = ""
        self.path = ""
        self.headers = {}
        self.body = ""
        self.query_params = {}
        self.form_data = {}
        self.path_params = {}
        self._parse_request(request_data)
        
    def _parse_request(self, request_data):
        # 分割请求头和请求体
        parts = request_data.split('\r\n\r\n', 1)
        if len(parts) == 2:
            headers, self.body = parts
        else:
            headers = parts[0]
            self.body = ""
            
        # 解析请求行
        lines = headers.split('\r\n')
        request_line = lines[0]
        self.method, self.path, _ = request_line.split(' ')
        
        # 解析查询参数
        if '?' in self.path:
            path_parts = self.path.split('?', 1)
            self.path = path_parts[0]
            query_string = path_parts[1]
            self.query_params = self._parse_params(query_string)
            
        # 解析头部
        for line in lines[1:]:
            if not line:
                continue
            key, value = line.split(': ', 1)
            self.headers[key] = value
            
        # 解析表单数据 (如果是POST请求)
        if self.method == 'POST':
            content_type = self.headers.get('Content-Type', '')
            if content_type == 'application/x-www-form-urlencoded':
                self.form_data = self._parse_params(self.body)
                
    def _parse_params(self, param_string):
        params = {}
        if not param_string:
            return params
            
        pairs = param_string.split('&')
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                params[key] = value
        return params

# 基础控制器类
class Controller:
    def __init__(self, app):
        self.app = app
        self.routes = {}
        
    def register_route(self, path, handler, methods=['GET']):
        """注册路由处理函数"""
        for method in methods:
            self.routes[(method, path)] = handler

# 应用类 - 管理服务器和路由
class MicroWebApp:
    def __init__(self):
        self.routes = {}
        self.controllers = {}
        
    def register_controller(self, name, controller):
        self.controllers[name] = controller
        
        for route_key, handler in controller.routes.items():
            method, path = route_key
            full_path = f"/{name}{path}"
            self.routes[(method, full_path)] = handler
    
    def register_route(self, path, handler, methods=['GET']):
        for method in methods:
            self.routes[(method, path)] = handler
    
    def handle_request(self, request_data):
        """处理HTTP请求并返回响应"""
        try:
            # 解析请求
            request = HTTPRequest(request_data)
            
            # 查找匹配的路由
            for (method, route_path), handler in self.routes.items():
                if method != request.method:
                    continue
                    
                # 检查路径是否匹配（支持路径参数）
                if self._match_path(route_path, request.path, request):
                    response = handler(request)
                    return self._build_response(response)
            
            return self._build_response("Not Found", status=404)
                
        except Exception as e:
            return self._build_response(f"Error: {str(e)}", status=500)
    
    def _match_path(self, route_path, request_path, request):
        """匹配路径并提取参数"""
        route_parts = route_path.rstrip('/').split('/')
        request_parts = request_path.rstrip('/').split('/')
        
        if len(route_parts) != len(request_parts):
            return False
            
        for rp, rqp in zip(route_parts, request_parts):
            if rp.startswith('<') and rp.endswith('>'):
                # 这是一个参数，提取参数名和值
                param_name = rp[1:-1]
                request.path_params[param_name] = rqp
            elif rp != rqp:
                return False
                
        return True
    
    def _build_response(self, body, status=200, content_type="text/html"):
        headers = f"HTTP/1.1 {status} OK\r\n"
        headers += f"Content-Type: {content_type}; charset=utf-8\r\n"  # 添加 charset=utf-8
        headers += "Connection: close\r\n\r\n"
        return headers + body

# BaseServer类 - 处理网络连接
class BaseServer:
    def __init__(self, app, host="0.0.0.0", port=80):
        self.app = app
        self.host = host
        self.port = port
        self.server_socket = None
        
    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        print(f"Server started on {self.host}:{self.port}")
        
        while True:
            conn, addr = self.server_socket.accept()
            print(f"Connection from {addr}")
            
            request = conn.recv(1024).decode('utf-8')
            if not request:
                conn.close()
                continue
                
            response = self.app.handle_request(request)
            conn.send(response.encode('utf-8'))
            conn.close()

# LED控制器
class LEDController(Controller):
    def __init__(self, app):
        super().__init__(app)
        self.led = LED()
        
        # 注册路由 - 支持GET和POST
        self.register_route("/", self.index, methods=['GET'])
        self.register_route("/on", self.led_on, methods=['GET'])
        self.register_route("/off", self.led_off, methods=['GET'])
        self.register_route("/blink", self.led_blink, methods=['GET'])
        self.register_route("/breathe", self.led_brightness, methods=['GET'])
        self.register_route("/stop", self.led_stop, methods=['GET'])
        self.register_route("/brightness/<level>", self.set_brightness, methods=['GET'])
        
    def read_html_template(self, template_name=None):
        """Read HTML template from file with error handling"""
        
        template_path = f"{template_name}"
        try:
            with open(template_path, 'r') as file:
                return file.read()
        except Exception as e:
            print(f"Error reading HTML template {template_path}: {e}")
            return ""
        
    def index(self, request):
        """LED控制面板 - 从html文件读取页面"""
        return self.read_html_template("index.html")
    
    def led_on(self, request):
        self.led.on()
        return """<html><body>
                <script>window.location.href='/led/';</script>
            </body></html>"""
         
    
    def led_stop(self, request):
        self.led.stop()

        return """<html><body>
                <script>window.location.href='/led/';</script>
            </body></html>"""
    
    def led_off(self, request):
        self.led.off()

        return """<html><body>
                <script>window.location.href='/led/';</script>
            </body></html>"""
        
    
    def led_blink(self, request):
        """LED闪烁"""
        # 测试闪烁功能
        print("测试闪烁功能...")
        self.led.blink(interval=0.4, brightness=30)
        time.sleep(3)
        self.led.stop()
        time.sleep(1)
        return """<html><body>
                <script>window.location.href='/led/';</script>
            </body></html>""" 

    def led_brightness(self, request):
        
        # 测试呼吸灯效果
        print("测试呼吸灯效果...")
        self.led.breathe(duration=3, max_brightness=50)
        time.sleep(6)  # 运行两个完整周期
        self.led.stop()
        time.sleep(1)
        return """<html><body>
                <script>window.location.href='/led/';</script>
            </body></html>"""
    
    def set_brightness(self, request):
        """设置LED亮度"""
        try:
            brightness_level = int(request.path_params['level'])
            # 确保亮度在0-100范围内
            brightness_level = max(0, min(100, brightness_level))
            
            # 转换为PWM值（假设你的LED类使用0-255范围）
            pwm_value = int(brightness_level * 2.55)
            self.led.set_brightness(pwm_value)
            
            return """<html><body>
                    <script>window.location.href='/led/';</script>
                </body></html>"""
        except (ValueError, KeyError):
            return self._build_response("Invalid brightness level", status=400)
# 主程序
def main():
    app = MicroWebApp()
    
    #wifi = WiFi()
    # 初始化WiFi连接
    #sta_if, ap_if = wifi.initialize()
    # 注册LED控制器
    led_controller = LEDController(app)
    
    
    app.register_controller("led", led_controller)
    
    # 添加首页重定向
    def home_redirect(request):
        return """<html><body>
            <h1>ESP32 Web Server</h1>
            <a href="/led/">前往LED控制页面</a>
        </body></html>"""
    
    app.register_route("/", home_redirect)
    
    # 创建并启动服务器
    server = BaseServer(app)
    server.start()

if __name__ == "__main__":
    main()
