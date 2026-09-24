import os
import json
import pandas as pd
from file_parser import parse_upload_file
from model_api import step_correct_all, one_step_correct
# 绘图内部已处理桌面路径
from visual_draw import draw_score_radar, draw_weak_bar, STAGE_AVERAGE


def batch_correct(file_list, stage, style, prompt_type, model_tag, output_csv_name="batch_result.csv"):
    # CSV报表保存到桌面，规避系统目录权限限制
    desktop_path = os.path.expanduser("~/Desktop")
    output_csv = os.path.join(desktop_path, output_csv_name)
    batch_result = []

    for idx, file in enumerate(file_list):
        essay_text = parse_upload_file(file)
        # 空文档容错处理
        if not essay_text.strip():
            batch_result.append({
                "文件名": file.name,
                "总分": "空文档",
                "语言": "",
                "逻辑": "",
                "素材": "",
                "立意": "",
                "评语": ""
            })
            continue
        # 根据提示词策略选择批改函数
        if "分步" in prompt_type:
            res = step_correct_all(essay_text, stage, style, model_tag)
        else:
            res = one_step_correct(essay_text, stage, style, model_tag)

        score = res["score_detail"]
        total = round(score["total"])
        # 仅传入图片文件名，绘图函数自动拼接桌面完整路径
        radar_path = draw_score_radar(score, f"radar_{idx}.png")
        weak_path = draw_weak_bar(score, STAGE_AVERAGE[stage], f"weak_{idx}.png")

        # 单篇结果记录
        row = {
            "文件名": file.name,
            "总分": total,
            "语言": score["lang"],
            "逻辑": score["logic"],
            "素材": score["material"],
            "立意": score["idea"],
            "错误数量": len(res["error_list"]),
            "综合评语": res["comment"],
            "雷达图路径": radar_path,
            "薄弱分析图路径": weak_path
        }
        batch_result.append(row)

    # 导出CSV到桌面
    df = pd.DataFrame(batch_result)
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    return batch_result, output_csv