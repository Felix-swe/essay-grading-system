import json
import streamlit as st
import os

@st.cache_data
def load_label_data():
    # 锁定当前项目目录，绝对不会读取C盘
    current_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_path, "essays.json")

    if not os.path.exists(file_path):
        st.error(f"数据集文件不存在：{file_path}")
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 强制为列表，适配你完整20条作文数据集
        if not isinstance(data, list):
            data = []

        return data

    except Exception as e:
        st.error(f"数据集读取失败：{str(e)}")
        return []