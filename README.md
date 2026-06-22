# 电子数据实验室 CNAS 设备管理系统

这是一个用于电子数据实验室 CNAS 设备管理的 Python 应用，保留与电子数据检验相关的设备台账能力，支持命令行和桌面 GUI。

## 保留功能

- 电子数据实验室设备新增、编辑、删除、查询
- 设备类别限定为电子数据相关类别
- 设备状态管理
- 校准/核查日期记录
- 维护、期间核查或状态备注
- CNAS 设备档案附件保存

## 设备类别

- 电子数据取证设备
- 数据恢复设备
- 存储介质检验设备
- 网络与日志分析设备
- 移动终端取证设备
- 写保护与复制设备
- 实验室通用设备
- 取证软件/许可证

## 快速开始

打开桌面 GUI：

```bash
python 电子数据实验室CNAS档案管理.py
```

或：

```bash
python 电子数据实验室CNAS档案管理.py gui
```

添加设备：

```bash
python 电子数据实验室CNAS档案管理.py equipment add --internal-id E001 --device-name "电子数据取证工作站" --category "电子数据取证设备" --room-number "1509" --status "在用"
```

更新设备：

```bash
python 电子数据实验室CNAS档案管理.py equipment update --internal-id E001 --status "维修中" --maintenance-notes "送检维修"
```

查询设备：

```bash
python 电子数据实验室CNAS档案管理.py equipment list
```

按关键字查询：

```bash
python 电子数据实验室CNAS档案管理.py equipment list --keyword "取证"
```

删除设备：

```bash
python 电子数据实验室CNAS档案管理.py equipment remove --internal-id E001
```

## 数据文件

默认数据保存到脚本同目录下的 `equipment_management.db`。

设备档案附件会复制到脚本同目录下的 `equipment_archives` 文件夹。

## 依赖

- Python 3.7+
- 仅使用 Python 标准库，无需安装第三方包
