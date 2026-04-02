# 🧠 NeuroScope - 多模态脑信号可视化分析平台

![Version](https://img.shields.io/badge/version-1.00-blue)
![Platform|116](https://img.shields.io/badge/platform-Windows-green)
`快速功能导航`： [EEG 源定位可视化](#eeg-源定位可视化) | [EEG 功能连接分析](#eeg-功能连接分析) | [fMRI 脑区激活定位](#fmri-脑区激活定位) | [fMRI 功能连接分析](#fmri-功能连接分析)

---

> **NeuroScope** 是一个面向教学展示、科研入门和竞赛答辩场景的 EEG/fMRI 脑可视化平台。系统强调统一界面、清晰流程和直观结果，无需编程基础即可实现多模态脑数据的自动化分析与交互式展示。本文档是面向用户所编辑的快速入门使用说明。
## 🔎系统使用数据集说明
### **使用规范声明**
> 本项目使用了EEG  `Biosemi`数据集，fMRI `ABIDE I` 与`REST-meta-MDD`数据集。本项目**未打包、未上传、未分发任何原始 EEG、fMRI 数据文件**，仅使用数据集进行算法验证与演示。所有数据集均来自国际权威脑科学公开平台，遵循对应开源协议使用。复现本项目需用户自行前往上述官方网址下载对应开源数据。

### **EEG 脑电信号分析数据集（OpenNeuro BioSemi）**
本项目 EEG 源定位与 EEG 功能连接模块采用国际公开开源数据集 OpenNeuro 26 By Biosemi 进行测试与验证。
- 官方开源地址：[OpenNeuro BioSemi](https://openneuro.org/datasets/ds005284/versions/1.0.0)
- 数据集 DOI：doi:10.18112/openneuro.ds005284.v1.0.0
- 本项目使用数据路径（原始开源数据集内路径）：
	ds005284/sub-{被试编号}/eeg/sub-{被试编号}_task-26ByBiosemi_eeg.bdf
- 数据格式：.bdf | 采样率：512Hz | 通道配置：64 标准 10-20 系统头皮脑电通道 + 眼电/心电辅助通道
- 实验任务：激光疼痛刺激任务态实验（固定强度激光刺激，每隔约 20 秒一次，共 16 次试验，参与者进行 0-10 疼痛评分）
- 用途：用于 EEG 源定位可视化验证、脑区时间序列提取、功能连接矩阵构建、3D 脑网络拓扑分析、可视化结果验证

### **fMRI 功能连接分析数据集（ABIDE I）**

本项目 fMRI 功能连接模块采用国际公开开源数据集 ABIDE I（Autism Brain Imaging Data Exchange I） 进行测试与验证。
- 官方开源地址：[ABIDE I](https://fcon_1000.projects.nitrc.org/indi/abide/abide_I.html](https://fcon_1000.projects.nitrc.org/indi/abide/abide_I.html)
- 本项目使用数据路径（原始开源数据集内路径）：
	ABIDE/ABIDE I/Yale/{被试编号}/session_1/rest_1/rest.nii.gz
- 数据格式：NIfTI（.nii.gz）
- 用途：用于脑功能连接计算、脑网络构建、滑动窗口动态功能连接验证

### **fMRI 脑区激活分析数据集（REST-meta-MDD）**

本项目 fMRI 脑区激活定位模块采用公开开源数据集 REST-meta-MDD 静息态 fMRI 分析数据集。
- 官方开源地址：[REST-meta-MDD](https://www.scidb.cn/detail?dataSetId=cbeb3c7124bf47a6af7b3236a3aaf3a8#p2)
- 本项目使用的数据路径（原始开源数据集内路径）：
	REST-meta-MDD-Phase1-Sharing/Results/ReHo_FunImgARglobalCWF/ReHoMap_*.nii.gz
- 数据格式：NIfTI（.nii.gz）
- 用途：用于脑区激活定位、激活强度统计、可视化结果验证

## 🚀 快速开始
### 1. 解压
将压缩包整体解压，确保main.exe与依赖文件_internal放在同一文件目录下
![[Pasted image 20260402192829.png]]
### 2. 系统要求
为确保图表渲染流畅，建议配置如下：
- **操作系统**: Windows 10/11 (64 位)
- **处理器**: Intel Core i7 或同级 AMD 处理器
- **内存**: 16GB RAM 及以上
- **显卡**: 独立显卡 (建议 NVIDIA RTX 系列)
- **存储**: 至少 3GB 可用空间

### 3. 启动项目
双击 main.exe 后等待程序运行，弹出软件界面则项目运行成功
![[Pasted image 20260402202021.png]]
## ✨ 核心功能 

### **EEG 源定位可视化**
左边栏选中第一个EEG源定位可视化
然后在输入栏填入或通过右方浏览文件按钮选中.bdf EEG文件以加载数据
下方有两栏可选分析参数，能够选择EEG截取的时长以及分析的EEG频段
调整好参数后点击下方执行EEG源定位即可开始分析
![[Pasted image 20260402221532.png]]
分析完后弹出交互式 EEG 源定位分析界面
用户可通过鼠标进行旋转、缩放等交互操作，并支持时间轴动画播放、调整播放速度、，可灵活切换双侧脑、单侧脑等多种观察视角以精确定位激活区域。
![[Pasted image 20260402223602.png|634]]
### **EEG 功能连接分析**

### **fMRI 脑区激活定位**
> [!warning]
> Lorem ipsum dolor sit amet

### **fMRI 功能连接分析**


## ❓ 常见问题 (FAQ)

**Q: 启动后提示模板文件缺失？**
A: 请确保网络连接正常，系统会在 `assets` 目录自动下载。若离线使用，请提前在有网环境下运行一次。

**Q: 支持 Mac 或 Linux 吗？**
A: 当前 Release 版本仅支持 Windows。源码支持跨平台编译，详见源码仓库。


---
*© 2025 NeuroScope Team. All Rights Reserved.*
