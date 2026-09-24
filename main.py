import streamlit as st
import pandas as pd

# 自定义业务模块
from model_api import step_correct_all, one_step_correct
from file_parser import parse_upload_file
from batch_process import batch_correct
# 新增导入两张对比柱状图绘图函数
from visual_draw import draw_score_radar, draw_weak_bar, STAGE_AVERAGE, draw_prompt_compare_bar, draw_model_compare_bar
from experiment import load_label_data

# 页面基础配置（必须放在最顶部）
st.set_page_config(page_title="AI作文批改系统", layout="wide")

# 侧边栏配置
with st.sidebar:
    st.header("批改参数设置")
    stage = st.selectbox("选择学段", ["小学", "初中", "高中", "大学"], key="sel_stage")
    comment_style = st.selectbox("评语风格", ["严肃学术风", "鼓励型风", "简洁型风"], key="sel_style")
    st.subheader("实验变量设置（课程对比实验）")
    # 对比1：一次性评分 / 分步评分 提示词策略
    prompt_strategy = st.radio("提示词策略", ["分步评分(多轮精准)", "一次性评分(单轮快速)"], key="radio_strategy")
    # 对比2：大模型 / 轻量模型 仅保留一组单选框
    model_mode = st.radio("模型模式", ["云端DeepSeek(big大模型)", "本地轻量模型(light)"], key="radio_model")
    # 统一判断模型标识
    if "big" in model_mode:
        model_tag = "big"
    else:
        model_tag = "light"

# 主页面标题
st.title("📝 在线智能作文批改系统")

# 分左右双栏
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("作文输入区")
    st.divider()
    st.subheader("📁 批量多文档批改模块")
    multi_files = st.file_uploader("批量上传多个Word/PDF文件", type=["pdf", "docx"], accept_multiple_files=True,
                                   key="batch_upload")
    batch_run = st.button("开始批量批改全部文档", type="secondary", key="btn_batch")
    # 修复：只传文件名，不再带./data路径
    if batch_run and multi_files:
        with st.spinner("批量批改中，请勿关闭页面..."):
            batch_data, csv_path = batch_correct(multi_files, stage, comment_style, prompt_strategy, model_tag,
                                                 "batch_output.csv")
            st.success(f"批量批改完成！共处理{len(multi_files)}篇作文，结果已导出至{csv_path}")
            # 展示批量结果表格
            st.dataframe(pd.DataFrame(batch_data))
            # 提供csv下载按钮
            with open(csv_path, "rb") as f:
                st.download_button(label="下载批量批改完整报表CSV", data=f, file_name="作文批量批改结果.csv",
                                   mime="text/csv")

    # 单篇输入模式切换
    input_mode = st.radio("输入方式", ["粘贴文本", "上传Word/PDF文件"], key="radio_input_mode")
    essay_text = ""
    if input_mode == "粘贴文本":
        essay_text = st.text_area("粘贴你的作文全文", height=380, key="ta_essay")
    else:
        uploaded_file = st.file_uploader("上传文档", type=["pdf", "docx"], key="upload_file")
        if uploaded_file is not None:
            # 调用file_parser.py解析文档
            essay_text = parse_upload_file(uploaded_file)
            st.success("文档解析完成，下方预览：")
            st.text(essay_text[:800] + "..." if len(essay_text) > 800 else essay_text)
    run_btn = st.button("开始AI批改", type="primary", key="btn_start_correct")

# 批改结果容器
result_container = col2.empty()

# 仅点击按钮后执行批改
if run_btn and essay_text.strip():
    with result_container.container():
        try:
            # 根据提示词策略选择对应批改函数，无重复覆盖
            if "分步" in prompt_strategy:
                result = step_correct_all(essay_text, stage, comment_style, model_tag)
                st.info("🔬 实验模式：分步多轮提示词批改")
            else:
                result = one_step_correct(essay_text, stage, comment_style, model_tag)
                st.info("🔬 实验模式：一次性单轮提示词批改")

            score_detail = result["score_detail"]
            # 总分四舍五入整数
            total_score = round(score_detail["total"])
            st.metric("作文综合总分", value=total_score)
            # 分项得分
            st.subheader("四项分项打分")
            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric("语言表达", score_detail["lang"])
            sc2.metric("逻辑结构", score_detail["logic"])
            sc3.metric("素材内容", score_detail["material"])
            sc4.metric("立意思想", score_detail["idea"])

            # 错误列表展示
            st.subheader("文本错误修正")
            err_list = result["error_list"]
            if isinstance(err_list, list) and len(err_list) > 0:
                for err in err_list:
                    err_type = err.get("type", "未知错误")
                    err_pos = err.get("pos", "未标注位置")
                    err_old = err.get("old", "无原文")
                    err_new = err.get("new", "无修改建议")
                    st.write(f"【{err_type}】位置{err_pos}：`{err_old}` → `{err_new}`")
            else:
                st.success("全文未检测到文字、标点、语法错误")

            # 拓展素材
            st.subheader("拓展写作素材")
            mat_list = result["material_list"]
            for mat in mat_list:
                st.markdown(f"- {mat}")

            # 修改建议
            st.subheader("优化修改建议")
            st.write(result["suggestions"])

            # 综合评语
            st.subheader("教师综合评语")
            st.info(result["comment"])

            # ==========修复缩进：可视化分析模块放到try正常分支，批改成功就展示==========
            st.divider()
            st.subheader("📊 作文可视化分析报告")
            # 生成雷达图+薄弱分析图
            radar_img_path = draw_score_radar(score_detail, "temp_radar.png")
            weak_img_path = draw_weak_bar(score_detail, STAGE_AVERAGE[stage], "temp_weak.png")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.image(radar_img_path, caption="四项得分雷达图")
                st.markdown("雷达解读：图形覆盖面积越大，综合写作能力越强；凹陷维度为薄弱项。")
            with col_r2:
                st.image(weak_img_path, caption="薄弱环节对比图")
                st.markdown("对比解读：低于橙色平均分的维度，为本篇作文重点提升方向。")

        except Exception as e:
            st.error(f"批改过程出错：{str(e)}")

# ==========对比实验说明面板==========
st.divider()
exp_btn = st.button("打开对比实验说明面板（课程作业）")
if exp_btn:
    with st.spinner("加载实验数据集..."):
        data = load_label_data()
        st.subheader("📊 双维度对比实验说明")
        st.markdown("""
        ### 实验1：提示词策略对比
        1. 分步评分：纠错、打分、素材推荐分3次独立API调用，输出JSON稳定、错误漏检少、打分精准，但请求耗时更长
        2. 一次性评分：单条请求完成全部批改任务，速度更快，但容易出现JSON解析失败、分数偏差、错别字遗漏

        ### 实验2：模型规模对比
        1. big大模型：逻辑结构识别、病句修正、主题素材匹配准确率更高，适合正式作文批改
        2. light轻量模型：本地离线运行、零成本，仅能识别简单错别字，复杂段落逻辑分析能力弱

        ### 实验操作规范（作业要求）
        固定同一篇作文、学段、评语风格，仅修改单一实验变量，记录四项分项分数、解析失败次数、错误检出数量，完成效果对比。
        """)
        st.success(f"实验数据集共 {len(data)} 篇作文样本，可批量完成对照测试")

        # 新增：单独生成两张对比柱状图按钮
        st.divider()
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            if st.button("生成【提示词策略对比柱状图】"):
                bar_path = draw_prompt_compare_bar()
                st.image(bar_path, caption="提示词策略指标对比柱状图")
                st.info(f"图片已保存至桌面 data_images 文件夹：{bar_path}")
        with col_exp2:
            if st.button("生成【模型规模对比柱状图】"):
                bar_path = draw_model_compare_bar()
                st.image(bar_path, caption="轻量/大模型批改指标对比柱状图")
                st.info(f"图片已保存至桌面 data_images 文件夹：{bar_path}")

# 功能按钮分区
st.divider()
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("一键清空全部缓存，重新批改", key="btn_clear_all_cache_top"):
        st.cache_data.clear()
        st.rerun()
with col_btn2:
    exp_btn2 = st.button("加载数据集查看(实验模块)", key="btn_load_dataset")
    if exp_btn2:
        with st.spinner("加载数据集..."):
            data = load_label_data()
            st.success(f"数据集加载完成，共{len(data)}篇作文样本")

# 底部缓存清空按钮
st.divider()
if st.button("一键清空全部缓存，重新批改", key="btn_clear_all_cache_bottom"):
    st.cache_data.clear()
    st.rerun()