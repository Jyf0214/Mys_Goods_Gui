# Mys Goods GUI

米游社商品兑换助手，支持 PyQt6 桌面版和 Flask 网页版两种界面。

## 分支说明

本仓库为 [mxyooR/Mys_Goods_Gui](https://github.com/mxyooR/Mys_Goods_Gui) 的 fork 分支，由下游作者 **Jyf0214** 维护。

| | 上游仓库 | 本仓库（fork） |
|---|---|---|
| 作者 | mxyooR | Jyf0214 |
| 仓库 | `mxyooR/Mys_Goods_Gui` | `Jyf0214/Mys_Goods_Gui` |
| 界面 | PyQt6 桌面版 | PyQt6 桌面版 + Flask 网页版 |

本 fork 在上游基础上新增了 **Flask 网页 GUI**，可直接通过浏览器访问，无需安装桌面环境。

## 功能特性

- **扫码登录** — 使用米游社 App 扫描二维码快速登录
- **手动登录** — 通过粘贴 Cookie 手动登录
- **商品浏览** — 按游戏分类浏览商品，查看价格和兑换时间
- **心愿单** — 将感兴趣的商品加入心愿单
- **定时兑换** — 创建兑换任务，设置精确兑换时间和请求次数
- **NTP 时间同步** — 使用 NTP 服务器校准时间，确保精确兑换
- **双界面支持** — PyQt6 桌面版 + Flask 网页版，功能一致

## 写在前面

感谢你使用 Mys Goods GUI。由于本人能力有限，项目可能仍然存在一些 bug，欢迎提交 issue，也请勿将本项目用于非法用途。希望这个项目对你有所帮助，并且欢迎提出改进建议。


## 安装与运行

### 先决条件

- Python 3.11+
- pip

---

### 方式一：Flask 网页版（推荐，无需桌面环境）

1. 克隆本仓库：

```bash
git clone https://github.com/Jyf0214/Mys_Goods_Gui.git
cd Mys_Goods_Gui/web_app
```

2. 安装依赖：

```bash
pip install -r requirements_web.txt
```

3. 启动服务：

```bash
python app.py
```

4. 浏览器打开 `http://localhost:5000`

---

### 方式二：PyQt6 桌面版

1. 克隆本仓库：

```bash
git clone https://github.com/Jyf0214/Mys_Goods_Gui.git
cd Mys_Goods_Gui/pyqt_app
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 运行应用：

```bash
python main.py
```

## 使用说明

### 1. 登录

**扫码登录（推荐）**
- 点击"生成二维码"
- 使用米游社 App 扫码
- 等待登录成功

**手动登录**
- 打开米游社网页版并登录
- 按 F12 打开开发者工具
- 在 Console 中输入 `document.cookie`
- 复制完整的 Cookie 粘贴到输入框
- 点击"登录"

### 2. 商品管理

1. 选择游戏类型
2. 浏览商品列表（显示图标、价格、兑换时间）
3. 点击"加入心愿单"添加感兴趣的商品

### 3. 任务管理

1. 点击"创建任务"
2. 从心愿单选择商品
3. 选择收货地址（游戏内商品选"空地址"）
4. 设置兑换时间（自动填充商品兑换时间）
5. 设置请求次数
6. 点击"创建"
7. 在任务列表中点击"启动"开始任务

### 4. 数据管理

**网页版**数据保存在 `web_app/data/`，**桌面版**数据保存在 `pyqt_app/data/`：

```
web_app/              # 或 pyqt_app/
├── data/
│   ├── config.json    # 登录配置
│   ├── tasks.json     # 任务列表
│   └── wishlist.json  # 心愿单
└── logs/
    └── app.log        # 应用日志
```



## 技术栈

### Flask 网页版
- **Flask** + **Flask-SocketIO** — Web 框架 + 实时通信
- **httpx** / **requests** — HTTP 客户端
- **ntplib** — NTP 时间同步
- **qrcode** — 二维码生成

### PyQt6 桌面版
- **PyQt6** — 桌面 GUI 框架
- **httpx** — 异步 HTTP 客户端
- **ntplib** — NTP 时间同步
- **qrcode** — 二维码生成



## 注意事项

- 兑换时间使用 NTP 时间同步，确保网络连接正常
- 本工具不受理也不会解决兑换状态码为1028或其他的问题
- 请勿用于非法用途

## 参考项目

本项目参考了以下开源项目：

- [mihoyo_login](https://github.com/Womsxd/mihoyo_login)
- [nonebot-plugin-mystool](https://github.com/Ljzd-PRO/nonebot-plugin-mystool)
- [Mys-Exchange-Goods](https://github.com/GOOD-AN/Mys-Exchange-Goods)
- [mihoyo-api-collect](https://github.com/UIGF-org/mihoyo-api-collect)
- [MihoyoBBSTools](https://github.com/Womsxd/MihoyoBBSTools)

## 免责声明

本 Mys Goods GUI 程序（以下简称"程序"）由用户编写，仅供学习和研究目的使用。在使用本程序前，请仔细阅读以下免责声明：

1. **使用风险**  
   使用本程序的风险由用户自行承担。程序的开发者不对因使用或无法使用本程序而产生的任何直接或间接损失承担任何责任。

2. **合法性**  
   用户在使用本程序时应遵守相关法律法规及服务提供商的使用条款。程序的开发者不对用户因使用本程序而违反任何法律法规或服务条款承担责任。

3. **责任限制**  
   在适用法律允许的最大范围内，程序的开发者不对因使用或无法使用本程序而导致的任何损害承担责任，包括但不限于利润损失、数据丢失或业务中断等。

通过下载、安装或使用本程序，用户即表示已阅读、理解并同意本免责声明的所有条款。如果用户不同意本免责声明中的任何条款，请不要使用本程序。

## License

GPL-3.0
