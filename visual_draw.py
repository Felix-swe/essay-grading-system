import os
import matplotlib.pyplot as plt
import numpy as np
# 文件末尾导出可用函数
__all__ = [
    "draw_score_radar",
    "draw_weak_bar",
    "draw_prompt_compare_bar",
    "draw_model_compare_bar",
    "STAGE_AVERAGE"
]
# 统一保存到桌面data_images文件夹，无系统权限限制
DESKTOP = os.path.expanduser("~/Desktop")
SAVE_DIR = os.path.join(DESKTOP, "data_images")
# 自动创建，已存在不会报错
os.makedirs(SAVE_DIR, exist_ok=True)

# 修复中文乱码
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

def draw_score_radar(score_data, file_name):
    full_path = os.path.join(SAVE_DIR, file_name)
    labels = ["语言表达", "逻辑结构", "素材内容", "立意思想"]
    values = [score_data["lang"], score_data["logic"], score_data["material"], score_data["idea"]]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"projection": "polar"})
    ax.plot(angles, values, linewidth=2, color="#2F5597", label="本次作文得分")
    ax.fill(angles, values, alpha=0.25, color="#2F5597")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylim(0, 100)
    ax.set_title("作文四项维度得分雷达图", fontsize=14, pad=20)
    ax.grid(True)
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(full_path, dpi=300)
    plt.close()
    return full_path

def draw_weak_bar(score_data, stage_avg, file_name):
    full_path = os.path.join(SAVE_DIR, file_name)
    labels = ["语言表达", "逻辑结构", "素材内容", "立意思想"]
    user_score = [score_data["lang"], score_data["logic"], score_data["material"], score_data["idea"]]
    avg_score = [stage_avg["lang"], stage_avg["logic"], stage_avg["material"], stage_avg["idea"]]
    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bar1 = ax.bar(x - width/2, user_score, width, color="#4472C4", label="本人作文得分")
    bar2 = ax.bar(x + width/2, avg_score, width, color="#ED7D31", label="同学段平均分")
    ax.bar_label(bar1, padding=2)
    ax.bar_label(bar2, padding=2)
    ax.set_title("作文薄弱环节对比分析图（个人VS学段平均）", fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(full_path, dpi=300)
    plt.close()
    return full_path

# 学段平均分配置
STAGE_AVERAGE = {
    "小学": {"lang":75, "logic":73, "material":70, "idea":72},
    "初中": {"lang":72, "logic":70, "material":68, "idea":71},
    "高中": {"lang":70, "logic":74, "material":72, "idea":69},
    "大学": {"lang":68, "logic":76, "material":75, "idea":67}
}
def draw_prompt_compare_bar(file_name="prompt_compare_bar.png"):
    """一次性评分 VS 分步评分 指标对比柱状图，单独生成图片"""
    full_path = os.path.join(SAVE_DIR, file_name)
    labels = ["JSON解析成功率(%)", "单篇平均耗时(s)", "错误标注完整率(%)"]
    one_time = [68, 4.2, 72]
    step_split = [96, 6.5, 94]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    rect1 = ax.bar(x - width/2, one_time, width, label="一次性整体提示词", color="#4472C4")
    rect2 = ax.bar(x + width/2, step_split, width, label="分步拆解提示词", color="#ED7D31")

    ax.bar_label(rect1, padding=3)
    ax.bar_label(rect2, padding=3)
    ax.set_title("一次性提示词 VS 分步提示词效果对比", fontsize=14, pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(full_path, dpi=300)
    plt.close()
    return full_path


def draw_model_compare_bar(file_name="model_compare_bar.png"):
    """本地轻量模型 VS 云端大模型 指标对比柱状图，单独生成图片"""
    full_path = os.path.join(SAVE_DIR, file_name)
    labels = ["纠错准确率(%)", "议论文打分精度(%)", "素材丰富度(满分100)", "单篇平均耗时(s)"]
    local_light = [86, 82, 70, 3.8]
    cloud_big = [95, 93, 92, 2.1]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(11, 6))
    bar1 = ax.bar(x - width/2, local_light, width, color="#2F5597", label="本地Qwen2.5-7B(轻量模型)")
    bar2 = ax.bar(x + width/2, cloud_big, width, color="#C00000", label="云端DeepSeek(大模型)")

    ax.bar_label(bar1, padding=2)
    ax.bar_label(bar2, padding=2)
    ax.set_title("本地轻量模型 VS 云端大模型批改效果对比", fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    ax.set_ylim(0, 105)

    plt.tight_layout()
    plt.savefig(full_path, dpi=300)
    plt.close()
    return full_path