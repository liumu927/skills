# 常见问题排查

本文档记录 Gradio Tab 开发中遇到的常见问题及解决方案。

## 目录

1. [Windows 控制台 Unicode 乱码](#windows-控制台-unicode-乱码tqdm-进度条)
2. [Python 环境配置](#python-环境配置)
3. [点云训练特殊处理](#点云训练---set-参数动态覆盖)

---

## Windows 控制台 Unicode 乱码（tqdm 进度条）

### 问题描述

在 Gradio 实时日志中，tqdm 进度条显示乱码：

```
[15:02:38] eval:   2%|��       |
```

### 原因

Windows 控制台默认使用 GBK 编码，无法正确显示 Unicode 方块字符（`█`, `▌`, `▎` 等）。

### 解决方案

在算法脚本（如 `test.py`）的开头添加 UTF-8 编码设置：

```python
import os
import sys

# 设置 UTF-8 编码以解决 Windows 控制台 Unicode 字符乱码问题
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ... 后续导入和代码 ...
```

**注意**：此设置必须在所有 `print()` 或 tqdm 输出之前执行。

### 参考实现

- `src/mc/train/first_stage.py` - 迷彩训练（已解决）
- `src/radar/OpenPCDdet-annotated_20240221/tools/test.py` - 点云训练（已解决）

---

## Python 环境配置

### 场景

当 Tab 需要使用特定的 conda 环境运行脚本时。

### 实现方式

在 `__init__` 中配置 Python 环境路径：

```python
import sys

def __init__(self):
    # ... 其他初始化 ...

    # 配置 Python 环境
    if os.name == "nt":
        self.python_env = "D:\\programFile\\anaconda3\\envs\\xxx_py38\\python.exe"
    else:
        self.python_env = os.path.join("/home/idrl/anaconda3/envs/xxx_py38", "bin", "python")

    if not os.path.exists(self.python_env):
        print(f"⚠️ 警告：Python环境不存在: {self.python_env}")
        self.python_env = None

def _get_python_env(self):
    """获取 Python 环境路径"""
    return self.python_env

def _start_task(self, *args):
    python_env = self._get_python_env() or sys.executable
    if self._get_python_env():
        self.log_handler.add_log(f"✅ 使用 Python 环境: {python_env}")
    else:
        self.log_handler.add_log("ℹ️ 使用当前 Python 环境")

    cmd = [python_env, script_path, ...]
```

### 参考实现

- `gradio_refactor/tabs/mc_train.py` - 迷彩训练环境
- `gradio_refactor/tabs/point_cloud_train.py` - 点云训练环境

---

## 点云训练 --set 参数动态覆盖

### 背景

点云训练的 `test.py` 使用 `.py` 配置文件，其中 `save_dir` 是硬编码的。可以通过 `--set` 参数动态覆盖：

```python
# test.py 支持的参数
parser.add_argument('--set', dest='set_cfgs', default=None, nargs=argparse.REMAINDER,
                    help='set extra config keys if needed')
```

### 实现方式

```python
def _start_training(self, *args):
    # ... 构建基础命令 ...

    # 添加保存路径（通过 --set 参数动态覆盖配置文件中的 save_dir）
    actual_save_path = save_path_val if save_path_val and save_path_val.strip() else self.default_save_path
    # ⚠️ 重要：Windows 路径必须转换为正斜杠
    actual_save_path = actual_save_path.replace("\\", "/")
    cmd.extend(["--set", "save_dir", actual_save_path])
    self.log_handler.add_log(f"📁 保存路径: {actual_save_path}")
```

### 关键注意事项

1. **Windows 路径必须转换**：`\` 转为 `/`，否则命令行参数解析会失败
2. **键必须已存在**：`cfg_from_list` 函数要求键必须已在配置中定义
3. **覆盖时机**：`--set` 参数在配置文件加载和子文件夹添加之后处理，会完全覆盖 `save_dir`

### 参考实现

- `gradio_refactor/tabs/point_cloud_train.py`
