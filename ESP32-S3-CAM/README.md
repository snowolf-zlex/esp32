
# 设备说明

ESP32-S3-CAM

![alt text](image.png)

![alt text](image-1.png)

ArudinoIDE配置要点：

![alt text](image-2.png)

可以使用`CameraWebServer`示例构建`相机网络服务`，代码配置注意要点：

``` arduino

#define CAMERA_MODEL_ESP32S3_EYE // Has PSRAM

```

自带RGBLED，使用LED_GPIO_NUM作为GPIO PIN控制
