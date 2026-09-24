import streamlit as st
import requests
import json
import re
import os

# ========== DeepSeek 云端全局配置 ==========
# API Key 从环境变量 DEEPSEEK_API_KEY 读取，避免硬编码泄露
# Windows PowerShell 设置：$env:DEEPSEEK_API_KEY = "你的密钥"
# Linux/macOS 设置：export DEEPSEEK_API_KEY="你的密钥"
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-chat"
TIMEOUT = 30

# 学段打分权重（匹配essays.json内human_detail分项）
STAGE_WEIGHT = {
    "小学": {"语言": 0.4, "逻辑": 0.2, "素材": 0.2, "立意": 0.2},
    "初中": {"语言": 0.3, "逻辑": 0.3, "素材": 0.25, "立意": 0.15},
    "高中": {"语言": 0.3, "逻辑": 0.3, "素材": 0.25, "立意": 0.15},
    "大学": {"语言": 0.2, "逻辑": 0.35, "素材": 0.35, "立意": 0.1}
}

# 评语风格模板
COMMENT_STYLE = {
    "严肃学术风": "客观严谨，全面指出缺陷，不使用鼓励性话术，适合高中、大学",
    "鼓励型风": "先大量表扬优点，温和委婉指出不足，语言亲切，适合中小学生",
    "简洁型风": "精简短句，只保留核心得分与关键修改点"
}


# ==================== 提示词模板（全部大括号转义，无format报错） ====================
# 一次性完整批改总提示词
def get_one_step_prompt(essay_text, stage, style):
    weight = STAGE_WEIGHT[stage]
    style_desc = COMMENT_STYLE[style]
    cut_essay = essay_text[:1000]
    prompt = f"""【硬性强制规则，违反任意一条输出作废，重新生成】
# 规则1 打分强制纯数字（最高优先级）
score_detail lang/logic/material/idea/total 只能填写0~100整数；
禁止写法："lang":"文字描述"，正确写法："lang":85

# 规则2 引号规范（解决嵌套语法报错）
素材、诗句引用文字**仅使用单引号 '内容'**；
双引号只允许作为JSON键名边界，内容内部禁止出现双引号 " "；
错误示例："素材"："3分钟读懂名著" | 正确示例："素材"：'三分钟读懂名著'

# 规则3 JSON顶层字段固定，禁止新增多余key
仅允许5个顶层键：error_list、score_detail、material_list、suggestions、comment
禁止生成 total_score、theme、materials、quotes、examples 等多余字段

# 规则4 输出格式约束
1. 仅输出单层独立JSON对象，禁止使用外层包装对象（例如不要用 {{"作文": 内容}} 包裹最终JSON）
2. 禁止```json、换行注释、前言后语、额外解释文字，只输出纯JSON
3. 所有大括号、中括号完整闭合，禁止半截截断

# 规则5 总分计算公式
total = (lang + logic + material + idea) ÷ 4，四舍五入取整数

【标准输出模板，严格模仿结构】
{{
"error_list": [{{"pos":"第1段第1句","old":"原文错误内容","new":"修正后文本","type":"语意重复"}}],
"score_detail": {{"lang":82,"logic":76,"material":85,"idea":79,"total":81}},
"material_list": ["中文素材1：'木心诗句内容'","中文素材2"],
"suggestions": ["分点中文修改建议"],
"comment": "{style_desc}风格完整中文评语"
}}

学段权重：语言{weight['语言'] * 100}%、逻辑{weight['逻辑'] * 100}%、素材{weight['素材'] * 100}%、立意{weight['立意'] * 100}%
作文原文：{cut_essay}"""
    return prompt


# 分步1：查找病句
def step_prompt_1_check_error(essay):
    cut_essay = essay[:1000]
    return f"""仅输出单层完整JSON数组，每条错误为完整{{"pos":"","old":"","new":"","type":""}}字典；
无多余文字、注释，括号完整闭合；
示例：[{{"pos":"第1段","old":"错字","new":"正确字","type":"错别字"}}]
作文：{cut_essay}"""


# 分步2：分项打分
def step_prompt_2_score(essay, stage):
    cut_essay = essay[:1000]
    return f"""仅输出0~100整数打分，禁止文字描述分数；
total = (lang+logic+material+idea)/4 四舍五入整数；
仅输出一行单层JSON，示例：{{"lang":82,"logic":76,"material":85,"idea":79,"total":81}}
作文：{cut_essay}"""


# 分步3：素材推荐
def step_prompt_3_material(essay, stage):
    cut_essay = essay[:1000]
    return f"输出适配{stage}学段素材完整JSON数组，无英文、数字，括号完整闭合：{cut_essay}"


# 分步4：生成修改建议
def step_prompt_4_suggest(error_json, score_json, essay):
    cut_essay = essay[:1000]
    return f"结合错误清单{error_json}、分项得分{score_json}，输出纯中文分点修改建议，无英文、完整不截断：{cut_essay}"


# 分步5：生成教师评语
def step_prompt_5_comment(score_json, suggest_text, style):
    return f"""全程中文撰写评语，无英文；风格：{COMMENT_STYLE[style]}，依据得分{score_json}、修改建议{suggest_text}生成完整评语。"""


# ==================== 修复版JSON解析核心函数（自动剥离外层嵌套+局部引号修复） ====================
def safe_load_json(raw_str, target_type="obj"):
    if not isinstance(raw_str, str):
        return None
    raw = raw_str.strip()

    # 清除代码块标记、换行、制表符
    raw = raw.replace("```json", "").replace("```", "")
    raw = raw.replace("\n", "").replace("\r", "")
    raw = raw.replace("\t", "")

    # 中文弯引号统一转单引号，源头减少冲突
    raw = raw.replace("“", "'")
    raw = raw.replace("”", "'")
    # 中文标点标准化为英文标点
    raw = raw.replace("，", ",")
    raw = raw.replace("：", ":")

    # 匹配完整JSON块
    if target_type == "obj":
        match_res = re.search(r'{[\s\S]*?}', raw)
    else:
        match_res = re.search(r'\[[\s\S]*?]', raw)

    if not match_res:
        print("【解析日志】未匹配有效JSON块")
        return None
    json_text = match_res.group()

    # 自动补 齐残缺括号，修复半截截断输出
    left_brace_cnt = json_text.count("{")
    right_brace_cnt = json_text.count("}")
    left_bracket_cnt = json_text.count("[")
    right_bracket_cnt = json_text.count("]")
    json_text += "}" * (left_brace_cnt - right_brace_cnt)
    json_text += "]" * (left_bracket_cnt - right_bracket_cnt)

    # 新增：正则自动剥离外层 {"作文": ...} 嵌套包装
    wrap_pattern = r'^\s*\{\s*"作文"\s*:\s*(.*)\s*\}\s*$'
    match_wrap = re.fullmatch(wrap_pattern, json_text, flags=re.DOTALL)
    if match_wrap:
        json_text = match_wrap.group(1).strip()
        print("【解析日志】已自动剥离外层{作文}嵌套包装")

    # 优先原生解析，合法JSON直接放行，不进入破坏性修复
    try:
        data = json.loads(json_text, strict=False)
        print("【解析日志】原生JSON解析成功，使用模型真实分数")
    except json.JSONDecodeError:
        print(f"【解析日志】原生JSON语法报错，启动局部引号修复：{json_text[:200]}")
        # 仅精准替换值内部违规双引号，保留合法单引号，不全局破坏
        fix_text = re.sub(r'(?<=:")(.*?)(?=",)', lambda m: m.group(1).replace('"', "'"), json_text)
        fix_text = re.sub(r'(?<=:")(.*?)(?="})', lambda m: m.group(1).replace('"', "'"), fix_text)
        try:
            data = json.loads(fix_text, strict=False)
            print("【解析日志】局部引号修复完成，读取真实分数")
        except Exception as e:
            print(f"【解析日志】修复后仍解析失败：{e}")
            return None

    # 剥离外层单键嵌套（通用包装）
    if isinstance(data, dict) and len(data) == 1:
        inner_key = list(data.keys())[0]
        inner_data = data[inner_key]
        if isinstance(inner_data, (dict, list)):
            data = inner_data

    # 自动删除模型私自新增的非法多余字段
    if isinstance(data, dict):
        extra_keys = ["total_score", "theme", "materials", "quotes", "examples", "data"]
        for k in extra_keys:
            if k in data:
                del data[k]

    # 打分对象容错：文字描述自动提取数字，不再直接判定失败兜底
    if target_type == "obj":
        if not isinstance(data, dict):
            print("【解析日志】打分输出非字典结构")
            return None
        # 键名兼容映射
        map_rule = {"language": "lang", "total_score": "total"}
        for old_key, new_key in map_rule.items():
            if old_key in data and new_key not in data:
                data[new_key] = data.pop(old_key)
        need_keys = ["lang", "logic", "material", "idea", "total"]
        if not all(k in data for k in need_keys):
            print(f"【解析日志】打分缺失必填字段，现有key：{list(data.keys())}")
            return None

        score_keys = ["lang", "logic", "material", "idea", "total"]
        for k in score_keys:
            val = data[k]
            # 字符串分值自动提取数字
            if isinstance(val, str):
                num_list = re.findall(r"\d+", val)
                if len(num_list) > 0:
                    val_num = int(num_list[0])
                    if 0 <= val_num <= 100:
                        data[k] = val_num
                        print(f"【解析日志】自动从文字'{val}'提取有效分值{val_num}")
                        continue
                print(f"【解析日志】字段{k}文字无法提取有效数字，违规值：{val}")
                return None
            # 校验分值区间0~100
            if not isinstance(val, (int, float)) or not (0 <= val <= 100):
                print(f"【解析日志】字段{k}分值超出合法区间，违规值：{val}")
                return None

        # 强制重算标准总分，覆盖模型错误total
        avg_total = (data["lang"] + data["logic"] + data["material"] + data["idea"]) / 4
        data["total"] = round(avg_total)

    # 错误数组过滤：仅保留标准错误字典
    if target_type == "arr" and isinstance(data, list):
        clean_arr = []
        for item in data:
            if isinstance(item, dict) and all(k in item for k in ["pos", "old", "new", "type"]):
                clean_arr.append(item)
        return clean_arr

    return data


# ==================== LLM 统一调用函数（Ollama全局规则强化） ====================
def llm_call(prompt, model_type="big"):
    # 本地 Ollama Qwen2.5-7B
    if model_type == "light":
        url = "http://127.0.0.1:11434/api/generate"
        strict_rule = """全局永久输出规则，违规作废重生成：
1. lang/logic/material/idea/total 仅允许0~100整数，禁止文字描述分数；
2. 文中引用只用单引号 ' '，内容内部严禁双引号 "；
3. JSON仅保留5个顶层key：error_list、score_detail、material_list、suggestions、comment；
4. 禁止生成total_score、theme等多余字段；
5. 只输出纯JSON，无代码块、解释文字；所有括号完整闭合；
6. total为四项平均分四舍五入整数。"""
        full_prompt = strict_rule + prompt
        payload = {
            "model": "qwen2.5:7b",
            "prompt": full_prompt,
            "stream": False,
            "temperature": 0.05,
            "num_ctx": 8192,
            "max_tokens": 1500
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            output_text = resp.json()["response"].strip()
            print("Ollama原始输出：", output_text)
            return output_text
        except requests.exceptions.ConnectTimeout:
            return '[{"pos":"系统提示","type":"本地服务异常","old":"Ollama未启动","new":"打开托盘Ollama程序"}]'
        except Exception as e:
            print(f"Ollama本地调用异常：{str(e)}")
            return '[{"pos":"系统提示","type":"推理失败","old":"模型输出异常","new":"重启Ollama重试"}]'

    # 云端 DeepSeek
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": """全局输出规范强制遵守：
1. 全文中文，禁止英文单词、句子；
2. lang/logic/material/idea/total只能输出0-100整数，禁止文字描述分数；
3. 仅单层完整JSON，无外层嵌套，括号完整闭合；
4. 数组元素必须为完整字典，禁止纯数字；
5. 不添加任何前言、后语、解释；
6. 引用内容只用单引号，禁止内层双引号，不生成total_score/theme多余字段。"""
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.01,
        "max_tokens": 4096
    }
    try:
        res = requests.post(API_URL, headers=headers, json=data, timeout=TIMEOUT)
        res.raise_for_status()
        resp_data = res.json()
        choices = resp_data.get("choices", [])
        if len(choices) == 0:
            return '[{"pos":"系统提示","type":"接口异常","old":"云端返回空内容","new":"缩短作文重新提交"}]'
        return choices[0]["message"]["content"].strip()
    except requests.exceptions.HTTPError as http_err:
        print(f"DeepSeek 400请求错误详情：{http_err.response.text if http_err.response else '无返回信息'}")
        return '[{"pos":"系统提示","type":"400参数错误","old":"请求文本超限/格式非法","new":"删减作文长度重试"}]'
    except requests.exceptions.ConnectTimeout:
        return '[{"pos":"系统提示","type":"网络异常","old":"云端接口超时","new":"切换手机热点"}]'
    except Exception as e:
        print(f"DeepSeek接口通用异常：{str(e)}")
        return '[{"pos":"系统提示","type":"接口调用失败","old":"API服务异常","new":"稍后重试"}]'


# ==================== 分步多轮批改入口 ====================
@st.cache_data(ttl=120, show_spinner="AI批改中...")
def step_correct_all(essay, stage, style, model_type="big"):
    default_score_template = {"lang": 70, "logic": 70, "material": 70, "idea": 70, "total": 70}
    # 1 错误列表
    err_raw = llm_call(step_prompt_1_check_error(essay), model_type)
    err_list = safe_load_json(err_raw, target_type="arr")
    if err_list is None or not isinstance(err_list, list):
        err_list = []

    # 2 分项打分
    score_raw = llm_call(step_prompt_2_score(essay, stage), model_type)
    score_data = safe_load_json(score_raw, target_type="obj")
    if score_data is None:
        print("【分步批改日志】打分JSON解析失败，启用兜底分数模板")
        score_data = default_score_template

    # 3 素材数组
    mat_raw = llm_call(step_prompt_3_material(essay, stage), model_type)
    mat_list = safe_load_json(mat_raw, target_type="arr")
    if mat_list is None or not isinstance(mat_list, list):
        mat_list = []

    # 4 修改建议、评语
    suggest_raw = llm_call(step_prompt_4_suggest(json.dumps(err_list), json.dumps(score_data), essay), model_type)
    comment_raw = llm_call(step_prompt_5_comment(json.dumps(score_data), suggest_raw, style))
    suggest_text = suggest_raw if isinstance(suggest_raw, str) else "修改建议生成异常"
    comment_text = comment_raw if isinstance(comment_raw, str) else "评语生成异常"

    return {
        "error_list": err_list,
        "score_detail": score_data,
        "material_list": mat_list,
        "suggestions": suggest_text,
        "comment": comment_text
    }


# ==================== 一次性单轮批改入口 ====================
@st.cache_data(ttl=180, show_spinner="AI批改中...")
def one_step_correct(essay, stage, style, model_type="big"):
    default_score_template = {"lang": 70, "logic": 70, "material": 70, "idea": 70, "total": 70}
    prompt = get_one_step_prompt(essay, stage, style)
    res_text = llm_call(prompt, model_type)
    parse_data = safe_load_json(res_text, target_type="obj")

    # 仅完全无法解析时启用兜底模板
    if not isinstance(parse_data, dict):
        print("【一次性批改日志】全局JSON解析失败，启用兜底分数模板")
        return {
            "error_list": [],
            "score_detail": default_score_template,
            "material_list": [],
            "suggestions": "模型输出格式违规，建议切换分步评分或重新提交作文",
            "comment": "批改解析失败，当前展示兜底参考分数"
        }

    # 组装标准化返回结构
    full_result = {
        "error_list": parse_data.get("error_list", []),
        "score_detail": parse_data.get("score_detail", default_score_template),
        "material_list": parse_data.get("material_list", []),
        "suggestions": parse_data.get("suggestions", "无修改建议"),
        "comment": parse_data.get("comment", "无评语")
    }
    # 统一重算标准总分
    sd = full_result["score_detail"]
    calc_total = round((sd["lang"] + sd["logic"] + sd["material"] + sd["idea"]) / 4)
    full_result["score_detail"]["total"] = calc_total
    return full_result