# 🧠 NeuroScope - 多模态脑信号可视化分析平台

![Version](https://img.shields.io/badge/version-1.00-blue)
![Platform|116](https://img.shields.io/badge/platform-Windows-green)

`快速功能导航`： [EEG 源定位可视化](#eeg-源定位可视化) | [EEG 功能连接分析](#eeg-功能连接分析) | [fMRI 脑区激活定位](#fmri-脑区激活定位) | [fMRI 功能连接分析](#fmri-功能连接分析)

> [!tip]
> 本文档包含多个演示动图，请耐心等待动图加载完成

---

> [!note]
> **NeuroScope** 是一个面向教学展示、科研入门和竞赛答辩场景的 EEG/fMRI 脑可视化平台。系统强调统一界面、清晰流程和直观结果，无需编程基础即可实现多模态脑数据的自动化分析与交互式展示。本文档是面向用户所编辑的快速入门使用说明。

## 🔎系统使用数据集说明
### **使用规范声明**
> [!note]
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
- 官方开源地址：[ABIDE I](https://fcon_1000.projects.nitrc.org/indi/abide/abide_I.html)
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
<img width="988" height="135" alt="file" src="https://github.com/user-attachments/assets/48962831-4ec2-40bd-9093-d470e2a5a063" />
### 2. 系统要求
为确保图表渲染流畅，建议配置如下：
- **操作系统**: Windows 10/11 (64 位)
- **处理器**: Intel Core i7 或同级 AMD 处理器
- **内存**: 16GB RAM 及以上
- **显卡**: 独立显卡 (建议 NVIDIA RTX 系列)
- **存储**: 至少 3GB 可用空间

### 3. 启动项目
双击 main.exe 后等待程序运行，弹出软件界面则项目运行成功
<img width="1500" height="975" alt="EEG SourceLocalization" src="https://github.com/user-attachments/assets/6cfa3b5f-68f5-449b-8d62-f1447a397b3c" />
## ✨ 核心功能 

### **EEG 源定位可视化**
左边栏选中第一个EEG源定位可视化
然后在输入栏填入或通过右方浏览文件按钮选中.bdf EEG文件以加载数据
下方有两栏可选分析参数，能够选择EEG截取的时长以及分析的EEG频段
调整好参数后点击下方执行EEG源定位即可开始分析
<img width="1500" height="975" alt="EEG SourceLocalization" src="https://github.com/user-attachments/assets/7729d33f-e1c4-490e-aa68-f50ae59d1a28" />
分析完后弹出交互式 EEG 源定位分析主图，该页面基于标准 fsaverage 模板脑，将 EEG 数据经 dSPM 源重建算法计算得到的皮层神经活动分布映射到三维大脑空间，生成可交互、多视角同步显示的皮层源定位图。它是 EEG 源定位分析中最核心的空间可视化结果。
图中通过颜色映射直观呈现脑皮层各区域的激活（电流密度）强度，暖色调代表高强度的神经电活动。用户可通过鼠标进行旋转、缩放等交互操作，并支持时间轴动画播放，可灵活切换双侧脑、单侧脑等多种观察视角以精确定位激活区域。
![eeg_source_localization_main](https://github.com/user-attachments/assets/c4198724-8438-4056-8dfc-55a8b92ea7c7)

同时在软件页面生成四类量化统计图表（时间曲线、功率谱、分布直方图与核心脑区排名），全方位解析头皮电信号在皮层空间的分布与动态演变。其中激活强度分布直方图因为数据量过大采用静态展示，另外三张统计图表[基于plotly可进行可交互展示](#接入plotly可交互图表),统计图表如下：
<img width="1348" height="757" alt="EEG1_1" src="https://github.com/user-attachments/assets/c11ebd12-d95e-4573-a2b4-13b2e2b4d68f" />
<img width="1347" height="748" alt="EEG1_2" src="https://github.com/user-attachments/assets/54d79695-b47c-4f85-9d53-fc2d5910d100" />
<img width="1345" height="741" alt="EEG1_3" src="https://github.com/user-attachments/assets/78e3bdf4-1bf7-4b9e-8082-7e9f8ed70e7a" />
<img width="1345" height="754" alt="EEG1_4" src="https://github.com/user-attachments/assets/332e7d8d-02f6-4ddd-9148-70cc4ef1e62f" />

### **EEG 功能连接分析**
左边栏选中第一个EEG源定位可视化
然后在输入栏填入或通过右方浏览文件按钮选中.bdf EEG文件以加载数据
下方有两栏可选分析参数，能够选择EEG截取的时长以及分析的EEG频段
调整好参数后点击下方执行EEG源定位即可开始分析
分析完后弹出交互式 EEG 脑网络三维主图：
本图在三维膨胀（inflation）皮层模型的基础上，将提取到的 68 个解剖脑区标记为网络节点，并将高强度的功能连接绘制为空间连线，构建了全脑功能交互的三维网络拓扑结构。图中节点的大小与颜色动态映射了该脑区的核心程度，而连线的粗细与颜色则直观反映了脑区间耦合强度的相对权重。用户可以在页面内自由旋转、平移和缩放模型，悬停查看任意节点的名称及其连接详情。
![eeg_conectivity](https://github.com/user-attachments/assets/a685b419-37d2-4994-9144-17b79595dd46)

同时在软件页面生成四类反映网络特性的统计图表（连接矩阵、枢纽排名、强度分布与距离相关性）。全方位解析EEG功能连接重要观测指标，所有统计图表均[基于plotly可进行可交互展示](#接入plotly可交互图表)：
<img width="1343" height="902" alt="EEG2_1" src="https://github.com/user-attachments/assets/61d507e2-aef0-4bc7-8503-4a8d269b0fc7" />
<img width="1349" height="752" alt="EEG2_2" src="https://github.com/user-attachments/assets/cfe3d25a-84ea-4a82-9b7d-7f70ffec44d2" />
<img width="1344" height="746" alt="EEG2_3" src="https://github.com/user-attachments/assets/a3a589d3-266c-4fb2-8674-656fc523a55a" />
<img width="1343" height="749" alt="EEG2_4" src="https://github.com/user-attachments/assets/314314ae-7d84-4e42-8cf3-8b003c4a5ebb" />

### **fMRI 脑区激活定位**
传入nii或nii.gz文件点击分析
分析完成后弹出交互式 fMRI 脑激活空间定位界面基于 MNI152 标准脑模板，将 fMRI 数据经统计计算得到的激活值映射到三维大脑空间，生成可交互、多视角同步显示的脑激活定位图，能够清晰、直观地呈现任务态或静息态下大脑的神经活动分布与强度差异，是 fMRI 激活分析中最核心、最常用的空间可视化结果。
![fMRI_Activation](https://github.com/user-attachments/assets/15b51928-6c34-4475-9110-6420e12883d7)

同时在软件页面生成两类图：阈值-体素数变化曲线以动画形式呈现阈值提升与激活体素数量下降的对应关系，提供了动画播放，暂停，重载的功能，方便使用者更细致地观察数据整体趋势和局部数据，直观展示结果；激活强度直方图呈现全脑体素激活强度分布，并以虚线自动标注 90% 显著性阈值，便于快速判断激活程度与显著性。所有统计图表均[基于plotly可进行可交互展示](#接入plotly可交互图表)
<img width="1341" height="754" alt="fMRI1_1" src="https://github.com/user-attachments/assets/54e621e0-6c73-422b-a170-0783cff21cb9" />
<img width="1348" height="750" alt="fMRI1_2" src="https://github.com/user-attachments/assets/1ee45082-f6d8-4854-84bd-ebb0d03638eb" />

### **fMRI 功能连接分析**
传入nii或nii.gz文件点击分析
分析完成后弹出交互式 3D 脑功能连接拓扑网络，本图基于 AAL 脑区分割模板的空间坐标，结合功能连接强度构建全脑三维交互脑网络模型，支持多角度、交互式观察，是 fMRI 功能连接分析中最直观、最具展示性的可视化形式，能够将抽象的脑区协同关系转化为可旋转、可缩放的三维空间网络结构，便于从整体视角把握大脑功能组织模式。
![fMRI_Conectivity](https://github.com/user-attachments/assets/adfbf661-b730-415f-ae99-f8d353c54857)

同时在软件页面生成四类反映fMRI功能连接的指标图，包括全脑功能连接矩阵热力图、正负连接比例饼图、滑动窗口四合一指标图（支持动画显示）、多窗口连接矩阵图集。所有统计图表均[基于plotly可进行可交互展示](#接入plotly可交互图表)：
<img width="1347" height="903" alt="fMRI2_1" src="https://github.com/user-attachments/assets/b3a38894-a8dc-454e-9fb4-459aec728480" />
<img width="1345" height="749" alt="fMRI2_2" src="https://github.com/user-attachments/assets/14ae2d13-035d-40f1-9b23-ac86ad42da14" />
<img width="1348" height="803" alt="fMRI2_3" src="https://github.com/user-attachments/assets/33ad18ee-9411-4131-b106-de79a9f454c6" />
<img width="1343" height="753" alt="fMRI2_4" src="https://github.com/user-attachments/assets/0e41d06c-0f5b-420f-9f31-c81768fcfadf" />

## ⚙️ 系统配置
### 接入plotly可交互图表
本项目大多数图表使用的是plotly可交互图表，基于html渲染，支持悬浮显示数据、框选缩放、自动调整大小、保存为html可交互图表与png静态图等基础操作。此外本系统对于部分统计图表增加了动画支持，用户可以播放、暂停与重载动画，以方便更好地观察数据趋势与局部细节。
![animate_demo](https://github.com/user-attachments/assets/116d2611-fa4f-4072-8923-699b149cb302)

### 卡片解释组件
每张可视化图表都提供图表解释文本与配图，帮助使用者更好地理解图表意义。
![card](https://github.com/user-attachments/assets/7087b797-2faa-42ef-8b8c-08d7dddbc160)

### 日志管理器
本项目使用日志管理器统一管理日志文件，支持清空、分类显示和下载的功能
![log_manager](https://github.com/user-attachments/assets/eb83f135-3703-4692-a6e7-9ae92e006596)

### 主题切换
本项目支持切换主题、主题色，以符合不同用户的使用习惯
![Theme_change](https://github.com/user-attachments/assets/14700ac3-a539-49c4-81d4-60964005836c)

## ❓ 常见问题 (FAQ)

**Q: 启动后提示模板文件缺失？**
A: 请确保网络连接正常，系统会在 `assets` 目录自动下载。若离线使用，请提前在有网环境下运行一次。

**Q: 支持 Mac 或 Linux 吗？**
A: 当前 Release 版本仅支持 Windows。源码支持跨平台编译，详见源码仓库。


---
*© 2026 NeuroScope Team. All Rights Reserved.*
