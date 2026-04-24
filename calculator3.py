# ===================== 安居房财务测算计算器（微信网页版-优化）=====================
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import json
import pandas as pd
# 👇 替换掉原来所有和volcengine相关的代码，只保留下面这些
import json
import pandas as pd
import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor

LLM_MODE = "cloud"   # "ollama" 或 "cloud"
CLOUD_PROVIDER = "kimi"
CLOUD_MODEL = "moonshot-v1-8k"

OLLAMA_MODEL = "qwen3.5:latest"

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

# ===================== 内置历史项目数据库 + 相似项目匹配 =====================
@st.cache_data
def load_builtin_history_projects():
    """
    内置历史项目库（先写在代码里，后续你有真实项目时，直接往这里补数据）
    字段尽量和AI补参所需字段一致
    """
    data = [
       {"项目名称":"历史出售项目A","项目子类型":"出售类","总建筑面积":52000,"总投资":51000,"售价":10500,"租金":0,"residential_area":0,"comm_area":4200,"park_count":460,"occupancy_stable":0.90,"comm_occupancy_stable":0.85,"park_occupancy_stable":0.90,"manage_coeff":1.92,"land_cost":13000,"construction_cost":5200,"infra_cost":450,"sale_area":41000,"comm_rent_start_price":32,"park_rent_start_price":300,"park_income_ratio":0.50},
       {"项目名称":"历史出售项目B","项目子类型":"出售类","总建筑面积":68000,"总投资":65000,"售价":9800,"租金":0,"residential_area":0,"comm_area":5000,"park_count":600,"occupancy_stable":0.90,"comm_occupancy_stable":0.86,"park_occupancy_stable":0.90,"manage_coeff":1.95,"land_cost":16500,"construction_cost":6700,"infra_cost":560,"sale_area":54000,"comm_rent_start_price":35,"park_rent_start_price":320,"park_income_ratio":0.55},
       {"项目名称":"乌坭浪","项目子类型":"出售类","总建筑面积":58380,"总投资":68397.84,"售价":12880,"租金":0,"residential_area":0,"comm_area":1750,"park_count":584,"occupancy_stable":0.90,"comm_occupancy_stable":0.90,"park_occupancy_stable":0.90,"manage_coeff":1.92,"land_cost":1308.71,"construction_cost":50240.70,"infra_cost":875.77,"sale_area":56105,"comm_rent_start_price":64,"park_rent_start_price":300,"park_income_ratio":0.50},
        {
            "项目名称": "历史出租项目A",
            "项目子类型": "出租类",
            "总建筑面积": 50000,
            "总投资": 48000,
            "售价": 0,
            "租金": 19.2,
            "residential_area": 43000,
            "comm_area": 2800,
            "park_count": 470,
            "occupancy_stable": 0.92,
            "comm_occupancy_stable": 0.85,
            "park_occupancy_stable": 0.90,
            "manage_coeff": 1.92,
            "land_cost": 12000,
            "construction_cost": 5000,
            "infra_cost": 420,
            "sale_area": 0,
            "comm_rent_start_price": 28,
            "park_rent_start_price": 300,
            "park_income_ratio": 0.50
        },
        {
            "项目名称": "历史出租项目B",
            "项目子类型": "出租类",
            "总建筑面积": 62000,
            "总投资": 59000,
            "售价": 0,
            "租金": 22.0,
            "residential_area": 54000,
            "comm_area": 3200,
            "park_count": 580,
            "occupancy_stable": 0.93,
            "comm_occupancy_stable": 0.86,
            "park_occupancy_stable": 0.91,
            "manage_coeff": 2.00,
            "land_cost": 15000,
            "construction_cost": 6200,
            "infra_cost": 500,
            "sale_area": 0,
            "comm_rent_start_price": 30,
            "park_rent_start_price": 320,
            "park_income_ratio": 0.55
        },
        {
            "项目名称": "历史租售结合项目A",
            "项目子类型": "租售结合类",
            "总建筑面积": 56000,
            "总投资": 54000,
            "售价": 9800,
            "租金": 18.5,
            "residential_area": 18000,
            "comm_area": 3500,
            "park_count": 500,
            "occupancy_stable": 0.90,
            "comm_occupancy_stable": 0.85,
            "park_occupancy_stable": 0.90,
            "manage_coeff": 1.92,
            "land_cost": 13500,
            "construction_cost": 5600,
            "infra_cost": 450,
            "sale_area": 28000,
            "comm_rent_start_price": 30,
            "park_rent_start_price": 300,
            "park_income_ratio": 0.50
        },
        {
            "项目名称": "历史租售结合项目B",
            "项目子类型": "租售结合类",
            "总建筑面积": 72000,
            "总投资": 70000,
            "售价": 11000,
            "租金": 20.0,
            "residential_area": 22000,
            "comm_area": 4500,
            "park_count": 680,
            "occupancy_stable": 0.91,
            "comm_occupancy_stable": 0.86,
            "park_occupancy_stable": 0.91,
            "manage_coeff": 1.98,
            "land_cost": 17500,
            "construction_cost": 7100,
            "infra_cost": 600,
            "sale_area": 36000,
            "comm_rent_start_price": 33,
            "park_rent_start_price": 320,
            "park_income_ratio": 0.55
        }
    ]
    return pd.DataFrame(data)


def _safe_num(x, default=0.0):
    try:
        if pd.isna(x):
            return default
        return float(x)
    except:
        return default


def find_similar_projects(core_input, history_df, top_n=3):
    """
    按项目子类型 + 面积 + 投资 + 售价/租金 + 结构比例 + 成本关键项做相似匹配
    """
    if history_df is None or history_df.empty:
        return pd.DataFrame()

    df = history_df.copy()
    target_type = core_input.get("项目子类型", "")
    if target_type:
        df = df[df["项目子类型"] == target_type]

    if df.empty:
        return pd.DataFrame()

    area0 = max(_safe_num(core_input.get("总建筑面积", 0)), 1)
    invest0 = max(_safe_num(core_input.get("总投资", 0)), 1)
    sale0 = _safe_num(core_input.get("售价", 0))
    rent0 = _safe_num(core_input.get("租金", 0))

    land0 = _safe_num(core_input.get("土地成本", 0))
    sale_ratio0 = _safe_num(core_input.get("可售面积占比", 0))
    comm_ratio0 = _safe_num(core_input.get("商业面积占比", 0))
    occ0 = _safe_num(core_input.get("住宅稳定期出租率", 0))
    comm_rent0 = _safe_num(core_input.get("商业起始租金", 0))

    def calc_score(row):
        score = 0.0
        row_area = max(_safe_num(row.get("总建筑面积", 0)), 1)

        # 1) 基础规模
        score += abs(_safe_num(row.get("总建筑面积")) - area0) / area0
        score += abs(_safe_num(row.get("总投资")) - invest0) / invest0

        # 2) 收入单价
        if sale0 > 0:
            score += abs(_safe_num(row.get("售价")) - sale0) / max(sale0, 1)
        if rent0 > 0:
            score += abs(_safe_num(row.get("租金")) - rent0) / max(rent0, 1)

        # 3) 成本结构
        if land0 > 0:
            score += abs(_safe_num(row.get("land_cost")) - land0) / max(land0, 1)

        # 4) 面积结构比例
        row_sale_ratio = _safe_num(row.get("sale_area", 0)) / row_area
        row_comm_ratio = _safe_num(row.get("comm_area", 0)) / row_area

        if sale_ratio0 > 0:
            score += abs(row_sale_ratio - sale_ratio0) / max(sale_ratio0, 0.01)
        if comm_ratio0 > 0:
            score += abs(row_comm_ratio - comm_ratio0) / max(comm_ratio0, 0.01)

        # 5) 运营关键参数
        if occ0 > 0:
            score += abs(_safe_num(row.get("occupancy_stable")) - occ0) / max(occ0, 0.01)
        if comm_rent0 > 0:
            score += abs(_safe_num(row.get("comm_rent_start_price")) - comm_rent0) / max(comm_rent0, 1)

        return score

    df["score"] = df.apply(calc_score, axis=1)
    df = df.sort_values("score").head(top_n).copy()
    df["weight"] = 1 / (df["score"] + 0.001)
    return df


def weighted_avg(similar_df, field, default_value):
    if similar_df is None or similar_df.empty or field not in similar_df.columns:
        return default_value
    vals = pd.to_numeric(similar_df[field], errors="coerce")
    weights = pd.to_numeric(similar_df["weight"], errors="coerce")
    valid = (~vals.isna()) & (~weights.isna())
    if valid.sum() == 0:
        return default_value
    return float(np.average(vals[valid], weights=weights[valid]))

def ai_fill_indicators(core_input, history_df=None):
    """
    AI补参：
    1）先按项目子类型生成规则默认值
    2）再用相似历史项目做加权修正
    3）最后叠加用户补充的关键参数
    """
    core = core_input
    total_area = _safe_num(core.get("总建筑面积", 50000))
    total_invest = _safe_num(core.get("总投资", 50000))
    operate_years = core.get("运营期年份", [2027, 2028, 2029])
    sub_type = core.get("项目子类型", "出租类")
    sale_price = _safe_num(core.get("售价", 0))
    rent_price = _safe_num(core.get("租金", 0))

    # 新增的AI核心输入
    user_land_cost = _safe_num(core.get("土地成本", 0))
    user_sale_ratio = _safe_num(core.get("可售面积占比", 0))
    user_comm_ratio = _safe_num(core.get("商业面积占比", 0))
    user_occ_stable = _safe_num(core.get("住宅稳定期出租率", 0))
    user_comm_rent = _safe_num(core.get("商业起始租金", 0))

    if not operate_years:
        operate_years = [2027, 2028, 2029]

    # ---------- 1）规则默认值 ----------
    if sub_type == "出售类":
        rule_params = {
            "residential_area": 0,
            "rent_increase_span": 3,
            "rent_increase_rate": 2.0,
            "ramp_years": operate_years[:2],
            "occupancy_ramp_dict": {int(y): (0.7 if i == 0 else 0.8) for i, y in enumerate(operate_years[:2])},
            "stable_start": (max(operate_years[:2]) + 1) if len(operate_years[:2]) > 0 else operate_years[0],
            "stable_end": operate_years[-1],
            "occupancy_stable": 0.9,

            "comm_area": total_area * 0.08,
            "comm_rent_start_price": 30.0,
            "comm_rent_increase_span": 3,
            "comm_rent_increase_rate": 3.0,
            "comm_occupancy_stable": 0.85,

            "park_count": int(total_area / 100),
            "park_rent_start_price": 300.0,
            "park_income_ratio": 0.5,
            "park_occupancy_stable": 0.9,

            "other_income_name": "其他收入",
            "other_income_total": total_invest * 0.003,

            "manage_coeff": 1.92,
            "land_cost": total_invest * 0.25,
            "construction_cost": total_area * 1000 / 10000,
            "infra_cost": total_area * 80 / 10000,
            "sale_area": total_area * 0.78,
            "sale_ramp_dict": {
                int(operate_years[0]): 0.3,
                int(operate_years[min(1, len(operate_years)-1)]): 0.4,
                int(operate_years[min(2, len(operate_years)-1)]): 0.3
            }
        }

    elif sub_type == "租售结合类":
        rule_params = {
            "residential_area": total_area * 0.35,
            "rent_increase_span": 3,
            "rent_increase_rate": 2.0,
            "ramp_years": operate_years[:2],
            "occupancy_ramp_dict": {int(y): (0.7 if i == 0 else 0.8) for i, y in enumerate(operate_years[:2])},
            "stable_start": (max(operate_years[:2]) + 1) if len(operate_years[:2]) > 0 else operate_years[0],
            "stable_end": operate_years[-1],
            "occupancy_stable": 0.9,

            "comm_area": total_area * 0.08,
            "comm_rent_start_price": 30.0,
            "comm_rent_increase_span": 3,
            "comm_rent_increase_rate": 3.0,
            "comm_occupancy_stable": 0.85,

            "park_count": int(total_area / 100),
            "park_rent_start_price": 300.0,
            "park_income_ratio": 0.5,
            "park_occupancy_stable": 0.9,

            "other_income_name": "其他收入",
            "other_income_total": total_invest * 0.003,

            "manage_coeff": 1.92,
            "land_cost": total_invest * 0.25,
            "construction_cost": total_area * 1000 / 10000,
            "infra_cost": total_area * 80 / 10000,
            "sale_area": total_area * 0.45,
            "sale_ramp_dict": {
                int(operate_years[0]): 0.3,
                int(operate_years[min(1, len(operate_years)-1)]): 0.4,
                int(operate_years[min(2, len(operate_years)-1)]): 0.3
            }
        }

    else:  # 出租类
        rule_params = {
            "residential_area": total_area * 0.88,
            "rent_increase_span": 3,
            "rent_increase_rate": 2.0,
            "ramp_years": operate_years[:2],
            "occupancy_ramp_dict": {int(y): (0.7 if i == 0 else 0.8) for i, y in enumerate(operate_years[:2])},
            "stable_start": (max(operate_years[:2]) + 1) if len(operate_years[:2]) > 0 else operate_years[0],
            "stable_end": operate_years[-1],
            "occupancy_stable": 0.9,

            "comm_area": total_area * 0.06,
            "comm_rent_start_price": 28.0,
            "comm_rent_increase_span": 3,
            "comm_rent_increase_rate": 3.0,
            "comm_occupancy_stable": 0.85,

            "park_count": int(total_area / 100),
            "park_rent_start_price": 300.0,
            "park_income_ratio": 0.5,
            "park_occupancy_stable": 0.9,

            "other_income_name": "其他收入",
            "other_income_total": total_invest * 0.003,

            "manage_coeff": 1.92,
            "land_cost": total_invest * 0.25,
            "construction_cost": total_area * 1000 / 10000,
            "infra_cost": total_area * 80 / 10000,
            "sale_area": 0,
            "sale_ramp_dict": {}
        }

    explain_list = ["已使用行业规则兜底"]

    # ---------- 2）相似项目修正 ----------
    similar_df = pd.DataFrame()
    if history_df is not None and not history_df.empty:
        similar_df = find_similar_projects(core_input, history_df, top_n=3)

    if similar_df is not None and not similar_df.empty:
        explain_list.append("已参考相似历史项目：" + "、".join(similar_df["项目名称"].tolist()))

        fields_to_adjust = [
            "residential_area", "comm_area", "park_count",
            "occupancy_stable", "comm_occupancy_stable", "park_occupancy_stable",
            "manage_coeff", "land_cost", "construction_cost", "infra_cost",
            "sale_area", "comm_rent_start_price", "park_rent_start_price", "park_income_ratio"
        ]

        for f in fields_to_adjust:
            if f in rule_params:
                rule_params[f] = weighted_avg(similar_df, f, rule_params[f])

    # ---------- 3）叠加用户关键输入 ----------
    applied_tags = []

    # 土地成本
    if user_land_cost > 0:
        rule_params["land_cost"] = user_land_cost
        applied_tags.append("土地成本")

    # 商业面积占比
    applied_comm_ratio = min(max(user_comm_ratio, 0.0), 0.95)

    # 可售面积占比
    applied_sale_ratio = min(max(user_sale_ratio, 0.0), 0.95)

    # 若租售结合/出售同时给了两个比例，避免超过100%
    if sub_type in ["出售类", "租售结合类"] and applied_sale_ratio > 0 and applied_comm_ratio > 0:
        total_ratio = applied_sale_ratio + applied_comm_ratio
        if total_ratio > 0.95:
            applied_sale_ratio = applied_sale_ratio / total_ratio * 0.95
            applied_comm_ratio = applied_comm_ratio / total_ratio * 0.95

    if applied_comm_ratio > 0:
        rule_params["comm_area"] = total_area * applied_comm_ratio
        applied_tags.append("商业面积占比")

    if sub_type in ["出售类", "租售结合类"] and applied_sale_ratio > 0:
        rule_params["sale_area"] = total_area * applied_sale_ratio
        applied_tags.append("可售面积占比")

    # 住宅稳定期出租率
    if sub_type in ["出租类", "租售结合类"] and user_occ_stable > 0:
        rule_params["occupancy_stable"] = min(max(user_occ_stable, 0.0), 1.0)
        applied_tags.append("住宅稳定期出租率")

    # 商业起始租金
    if user_comm_rent > 0:
        rule_params["comm_rent_start_price"] = user_comm_rent
        applied_tags.append("商业起始租金")

    # ---------- 4）类型修正 ----------
    if sub_type == "出售类":
        rule_params["residential_area"] = 0
        if sale_price <= 0:
            rule_params["sale_area"] = total_area * 0.78

    if sub_type == "出租类":
        rule_params["sale_area"] = 0

    # 整数修正
    rule_params["park_count"] = int(round(rule_params["park_count"], 0))

    if applied_tags:
        explain_list.append("已采用用户补充关键参数：" + "、".join(applied_tags))

    return rule_params, "；".join(explain_list)

def build_ai_assumption_table(core_input, ai_params, similar_projects=None):
    """
    生成AI补参说明表：哪些是用户输入，哪些是AI推断
    """
    similar_count = len(similar_projects) if similar_projects else 0
    infer_source = f"AI推断（参考{similar_count}个同类项目 + 行业规则）" if similar_count > 0 else "AI推断（行业规则）"

    def source_if_user(key, infer=infer_source):
        return "用户输入" if _safe_num(core_input.get(key, 0)) > 0 else infer

    rows = [
        {"参数": "项目子类型", "取值": core_input.get("项目子类型", ""), "来源": "用户输入"},
        {"参数": "总建筑面积(㎡)", "取值": core_input.get("总建筑面积", 0), "来源": "用户输入"},
        {"参数": "总投资(万元)", "取值": core_input.get("总投资", 0), "来源": "用户输入"},
        {"参数": "借款年利率(%)", "取值": core_input.get("借款年利率", 0), "来源": "用户输入"},
        {"参数": "折现率(%)", "取值": core_input.get("折现率", 0), "来源": "用户输入"},
    ]

    # 动态显示用户核心输入
    if _safe_num(core_input.get("土地成本", 0)) > 0:
        rows.append({"参数": "土地成本(万元)", "取值": core_input.get("土地成本", 0), "来源": "用户输入"})

    if _safe_num(core_input.get("售价", 0)) > 0:
        rows.append({"参数": "售价(元/㎡)", "取值": core_input.get("售价", 0), "来源": "用户输入"})

    if _safe_num(core_input.get("租金", 0)) > 0:
        rows.append({"参数": "住宅租金(元/㎡/月)", "取值": core_input.get("租金", 0), "来源": "用户输入"})

    if _safe_num(core_input.get("可售面积占比", 0)) > 0:
        rows.append({"参数": "可售面积占比(%)", "取值": round(core_input.get("可售面积占比", 0) * 100, 2), "来源": "用户输入"})

    if _safe_num(core_input.get("商业面积占比", 0)) > 0:
        rows.append({"参数": "商业面积占比(%)", "取值": round(core_input.get("商业面积占比", 0) * 100, 2), "来源": "用户输入"})

    if _safe_num(core_input.get("住宅稳定期出租率", 0)) > 0:
        rows.append({"参数": "住宅稳定期出租率(%)", "取值": round(core_input.get("住宅稳定期出租率", 0) * 100, 2), "来源": "用户输入"})

    if _safe_num(core_input.get("商业起始租金", 0)) > 0:
        rows.append({"参数": "商业起始租金(元/㎡/月)", "取值": core_input.get("商业起始租金", 0), "来源": "用户输入"})

    # AI补参与最终采用值
    rows.extend([
        {"参数": "住宅面积(㎡)", "取值": round(ai_params.get("residential_area", 0), 2), "来源": infer_source},
        {"参数": "商业面积(㎡)", "取值": round(ai_params.get("comm_area", 0), 2), "来源": source_if_user("商业面积占比")},
        {"参数": "车位数量", "取值": int(ai_params.get("park_count", 0)), "来源": infer_source},
        {"参数": "住宅稳定期出租率", "取值": round(ai_params.get("occupancy_stable", 0), 4), "来源": source_if_user("住宅稳定期出租率")},
        {"参数": "商业稳定期出租率", "取值": round(ai_params.get("comm_occupancy_stable", 0), 4), "来源": infer_source},
        {"参数": "车位稳定期出租率", "取值": round(ai_params.get("park_occupancy_stable", 0), 4), "来源": infer_source},
        {"参数": "管理系数", "取值": round(ai_params.get("manage_coeff", 0), 4), "来源": infer_source},
        {"参数": "土地成本(万元)", "取值": round(ai_params.get("land_cost", 0), 2), "来源": source_if_user("土地成本")},
        {"参数": "建安工程费(万元)", "取值": round(ai_params.get("construction_cost", 0), 2), "来源": infer_source},
        {"参数": "基础设施费(万元)", "取值": round(ai_params.get("infra_cost", 0), 2), "来源": infer_source},
        {"参数": "可售面积(㎡)", "取值": round(ai_params.get("sale_area", 0), 2), "来源": source_if_user("可售面积占比")},
        {"参数": "商业起始租金(元/㎡/月)", "取值": round(ai_params.get("comm_rent_start_price", 0), 2), "来源": source_if_user("商业起始租金")},
        {"参数": "车位起始租金(元/个/月)", "取值": round(ai_params.get("park_rent_start_price", 0), 2), "来源": infer_source},
        {"参数": "车位收入系数", "取值": round(ai_params.get("park_income_ratio", 0), 4), "来源": infer_source},
    ])
    return pd.DataFrame(rows)


def build_ai_summary_text(core_input, project_type, total_income, total_cost, total_net_profit, irr_value, total_npv_sum, similar_projects=None):
    """
    生成AI测算说明文字
    """
    sub_type = core_input.get("项目子类型", "")
    total_area = core_input.get("总建筑面积", 0)
    total_invest = core_input.get("总投资", 0)
    sale_price = core_input.get("售价", 0)
    rent_price = core_input.get("租金", 0)

    similar_projects = similar_projects or []
    similar_count = len(similar_projects)
    similar_names = "、".join([x.get("项目名称", "") for x in similar_projects[:3]]) if similar_count > 0 else "暂无"

    if sub_type == "出售类":
        income_desc = f"本次以出售类项目逻辑进行测算，核心售价输入为 {sale_price} 元/㎡。"
    elif sub_type == "出租类":
        income_desc = f"本次以出租类项目逻辑进行测算，核心租金输入为 {rent_price} 元/㎡/月。"
    else:
        income_desc = f"本次以租售结合类项目逻辑进行测算，核心售价为 {sale_price} 元/㎡，租金为 {rent_price} 元/㎡/月。"

    text = f"""
根据您给出的核心指标，系统已完成本项目的自动补参与财务测算。

其中，项目子类型为【{sub_type}】，总建筑面积约【{total_area}㎡】，总投资约【{total_invest}万元】。  
{income_desc}

本次测算共参考了【{similar_count}】个同类历史项目，主要参考项目包括：{similar_names}。  
在此基础上，系统对住宅面积、商业面积、车位数量、稳定期出租率、土地成本、建安工程费等参数进行了自动补齐，并生成了完整的收入、成本、税金、损益及现金流表。

测算结果显示：项目全周期总收入约为【{total_income}万元】，总成本费用约为【{total_cost}万元】，净利润约为【{total_net_profit}万元】，净现值约为【{total_npv_sum}万元】，全投资内部收益率（IRR）为【{irr_value}】。

请注意：以上结果属于“基于核心指标 + 历史样本 + 规则补参”的快速测算结果，适合用于前期方案研判、项目比选和初步汇报。如需正式决策，建议再结合人工校核对关键参数进行修正。
""".strip()

    return text


def build_ai_context_text(context_dict):
    """
    把当前测算结果整理成聊天上下文
    """
    if not context_dict:
        return "暂无测算上下文。"

    similar_names = "、".join(context_dict.get("similar_project_names", [])) if context_dict.get("similar_project_names") else "暂无"

    return f"""
项目类型：{context_dict.get("project_type", "")}
项目子类型：{context_dict.get("sub_type", "")}
总建筑面积：{context_dict.get("total_build_area", 0)}㎡
总投资：{context_dict.get("total_investment", 0)}万元
售价：{context_dict.get("sale_price", 0)}元/㎡
租金：{context_dict.get("rent_price", 0)}元/㎡/月
参考项目：{similar_names}

测算结果：
- 全周期总收入：{context_dict.get("total_income", 0)}万元
- 全周期总成本：{context_dict.get("total_cost", 0)}万元
- 全周期净利润：{context_dict.get("total_net_profit", 0)}万元
- 净现值：{context_dict.get("total_npv_sum", 0)}万元
- IRR：{context_dict.get("irr_value", "")}
- 利息保障倍数：{context_dict.get("interest_coverage_ratio", 0)}
""".strip()


def answer_ai_chat_local(question, context_dict):
    """
    本地版问答：支持异常解释、优化建议、参考项目说明、指标解释
    """
    q = (question or "").strip()
    if not q:
        return "请先输入问题。"

    total_income = float(context_dict.get("total_income", 0) or 0)
    total_cost = float(context_dict.get("total_cost", 0) or 0)
    total_net_profit = float(context_dict.get("total_net_profit", 0) or 0)
    total_npv_sum = float(context_dict.get("total_npv_sum", 0) or 0)
    irr_value = context_dict.get("irr_value", "")
    interest_coverage_ratio = float(context_dict.get("interest_coverage_ratio", 0) or 0)
    similar_project_names = context_dict.get("similar_project_names", [])
    sub_type = context_dict.get("sub_type", "")

    insight = build_risk_and_suggestion_text(context_dict)
    risk_text = insight["risk_text"]
    suggestion_text = insight["suggestion_text"]

    q_lower = q.lower()

    if "为什么" in q or "异常" in q or "不好" in q or "偏低" in q or "偏弱" in q:
        return f"从当前测算结果看，主要原因可能是：{risk_text}"

    if "建议" in q or "优化" in q or "怎么改" in q or "怎么提升" in q:
        return f"基于当前测算结果，我建议优先从这些方向优化：{suggestion_text}"

    if "收入" in q:
        return f"本项目全周期总收入约为 {total_income} 万元。若你愿意，我可以继续按住宅、车位、销售、商业出租几个模块帮你解释收入来源。"

    if "成本" in q:
        return f"本项目全周期总成本费用约为 {total_cost} 万元。当前如果项目收益偏弱，通常需要优先检查土地成本、建安成本、基础设施费和融资成本。"

    if "净利润" in q or "利润" in q:
        return f"本项目全周期净利润约为 {total_net_profit} 万元。若净利润偏低或为负，通常说明收入释放不足或成本压力较大。"

    if "净现值" in q or "npv" in q_lower:
        return f"本项目净现值约为 {total_npv_sum} 万元。{risk_text}"

    if "irr" in q_lower or "收益率" in q:
        return f"本项目全投资内部收益率（IRR）为 {irr_value}。如果IRR偏低，通常与前期投资过大、运营现金流不足、租售价格偏低或回收周期过长有关。"

    if "利息保障" in q or "偿债" in q:
        return f"本项目利息保障倍数约为 {interest_coverage_ratio}。一般来说，该指标越高，项目对利息支出的覆盖能力越强。当前判断为：{risk_text}"

    if "历史项目" in q or "参考项目" in q or "同类项目" in q:
        if similar_project_names:
            return f"本次测算主要参考了这些同类项目：{'、'.join(similar_project_names)}。这些样本被用于修正住宅面积、商业面积、车位数量、稳定出租率和部分成本参数。"
        return "本次测算未匹配到可用的同类历史项目，当前结果主要基于规则参数进行了补齐。"

    if "项目类型" in q or "子类型" in q:
        return f"当前测算项目子类型为 {sub_type}。不同子类型会影响收入结构、销售逻辑和补参规则。"

    if "怎么测" in q or "怎么来的" in q or "依据" in q:
        return "当前测算逻辑是：先根据你输入的核心指标匹配同类历史项目，再结合行业规则自动补齐缺失参数，最后进入完整财务模型生成收入、成本、税金、损益和现金流表。"

    return (
        "我已经拿到当前项目的测算上下文。"
        "你可以继续问我：为什么IRR为负、净现值为什么偏低、有哪些优化建议、参考了哪些历史项目、如何提升收益或改善偿债能力。"
    )

def build_ai_table_digest(project_type, income_df, total_cost_df, loan_df, profit_df, cf_df, tax_df=None, rental_cost_df=None):
    """
    把核心表格压缩成适合大模型理解的摘要
    """
    digest = {}

    # 收入结构
    income_items = {
        "住宅租金收入": _safe_get_sum(income_df, "住宅租金收入(万元)"),
        "车位收入": _safe_get_sum(income_df, "车位收入(万元)"),
        "配保房销售收入": _safe_get_sum(income_df, "配保房销售收入(万元)"),
        "商业出租收入": _safe_get_sum(income_df, "商业出租收入(万元)"),
        "出租净收益现值": _safe_get_sum(income_df, "出租净收益现值(万元)"),
        "总收入": _safe_get_sum(income_df, "总收入(万元)")
    }
    digest["income_items"] = income_items
    digest["top_income_items"] = _top_n_dict(
        {k: v for k, v in income_items.items() if k != "总收入" and v != 0},
        n=3
    )

    # 成本结构
    cost_candidates = {}
    if total_cost_df is not None:
        for col in total_cost_df.columns:
            if "万元" in col and "总成本费用" not in col:
                cost_candidates[col] = _safe_get_sum(total_cost_df, col)

    digest["top_cost_items"] = _top_n_dict(
        {k: v for k, v in cost_candidates.items() if v != 0},
        n=5
    )
    digest["total_cost"] = _safe_get_sum(total_cost_df, "总成本费用(不含建设期财务费用、不含税金)(万元)")

    # 财务费用
    digest["interest_total"] = _safe_get_sum(loan_df, "本期付息(万元)")
    digest["repay_total"] = _safe_get_sum(loan_df, "本期还本(万元)")

    # 利润与税
    digest["profit_total"] = _safe_get_sum(profit_df, "净利润(万元)")
    digest["profit_before_tax_total"] = _safe_get_sum(profit_df, "利润总额(万元)")
    digest["income_tax_total"] = _safe_get_sum(profit_df, "所得税(万元)")
    digest["tax_total"] = _safe_get_sum(tax_df, "税金及其附加总和(万元)") if tax_df is not None else 0.0

    # 现金流关键年份
    net_cf_years = {}
    npv_years = {}
    if cf_df is not None:
        for y in cf_df.index:
            try:
                net_cf_years[int(y)] = _round2(cf_df.loc[y, "净现金流量(万元)"], 0.0)
            except:
                pass
            try:
                npv_years[int(y)] = _round2(cf_df.loc[y, "净现值(万元)"], 0.0)
            except:
                pass

    digest["worst_net_cf_years"] = _top_n_dict(
        {k: v for k, v in net_cf_years.items() if v < 0},
        n=3
    )
    digest["best_net_cf_years"] = _top_n_dict(
        {k: v for k, v in net_cf_years.items() if v > 0},
        n=3
    )

    # 出售类补充：出租经营情况
    if rental_cost_df is not None and not rental_cost_df.empty:
        digest["rental_operation"] = {
            "商业出租收入合计": _safe_get_sum(rental_cost_df, "商业出租收入(万元)"),
            "出租营运成本合计": _safe_get_sum(rental_cost_df, "出租营运成本合计(万元)"),
            "出租经营税金合计": _safe_get_sum(rental_cost_df, "出租经营税金合计(万元)"),
            "出租净收入合计": _safe_get_sum(rental_cost_df, "出租净收入(万元)"),
            "出租净收益现值合计": _safe_get_sum(rental_cost_df, "出租净收益现值(万元)")
        }

    digest["project_type"] = project_type
    return digest

def build_ai_enhanced_context_text(context_dict):
    """
    生成更贴表格的上下文文本
    """
    if not context_dict:
        return "暂无测算上下文。"

    table_digest = context_dict.get("table_digest", {})
    similar_names = "、".join(context_dict.get("similar_project_names", [])) if context_dict.get("similar_project_names") else "暂无"

    top_income_text = "；".join([f"{k}={v}万元" for k, v in table_digest.get("top_income_items", [])]) or "暂无"
    top_cost_text = "；".join([f"{k}={v}万元" for k, v in table_digest.get("top_cost_items", [])]) or "暂无"
    worst_cf_text = "；".join([f"{k}年={v}万元" for k, v in table_digest.get("worst_net_cf_years", [])]) or "暂无"
    best_cf_text = "；".join([f"{k}年={v}万元" for k, v in table_digest.get("best_net_cf_years", [])]) or "暂无"

    rental_operation = table_digest.get("rental_operation", {})

    rental_text = ""
    if rental_operation:
        rental_text = f"""
出租经营补充：
- 商业出租收入合计：{rental_operation.get("商业出租收入合计", 0)}万元
- 出租营运成本合计：{rental_operation.get("出租营运成本合计", 0)}万元
- 出租经营税金合计：{rental_operation.get("出租经营税金合计", 0)}万元
- 出租净收入合计：{rental_operation.get("出租净收入合计", 0)}万元
- 出租净收益现值合计：{rental_operation.get("出租净收益现值合计", 0)}万元
""".strip()

    return f"""
项目类型：{context_dict.get("project_type", "")}
项目子类型：{context_dict.get("sub_type", "")}
总建筑面积：{context_dict.get("total_build_area", 0)}㎡
总投资：{context_dict.get("total_investment", 0)}万元
售价：{context_dict.get("sale_price", 0)}元/㎡
租金：{context_dict.get("rent_price", 0)}元/㎡/月
参考项目：{similar_names}

核心测算结果：
- 全周期总收入：{context_dict.get("total_income", 0)}万元
- 全周期总成本：{context_dict.get("total_cost", 0)}万元
- 全周期净利润：{context_dict.get("total_net_profit", 0)}万元
- 净现值：{context_dict.get("total_npv_sum", 0)}万元
- IRR：{context_dict.get("irr_value", "")}
- 利息保障倍数：{context_dict.get("interest_coverage_ratio", 0)}

收入结构重点：
- 主要收入项：{top_income_text}

成本结构重点：
- 主要成本项：{top_cost_text}

现金流重点：
- 负向现金流较大的年份：{worst_cf_text}
- 正向现金流较大的年份：{best_cf_text}

{rental_text}
""".strip()

def build_general_project_chat_context(
    project_type,
    total_build_area,
    total_investment,
    sale_avg_price,
    rent_start_price,
    total_income,
    total_cost,
    total_net_profit,
    total_npv_sum,
    irr_value,
    interest_coverage_ratio,
    income_df,
    total_cost_df,
    loan_df,
    profit_df,
    cf_df,
    history_df=None,
    tax_df=None,
    rental_cost_df=None,
    residential_area=0,
    comm_area=0,
    sale_area=0,
    comm_rent_start_price=0
):
    """
    给所有模式统一生成问答上下文
    """
    # 1. 统一映射子类型
    if project_type == "出售类(配保房/可售型人才房等)":
        sub_type = "出售类"
    elif project_type == "出租型(协议出让/合作类等)":
        sub_type = "出租类"
    else:
        sub_type = "租售结合类"

    # 2. 普通模式也尝试匹配历史项目
    core_input = {
        "项目子类型": sub_type,
        "总建筑面积": total_build_area,
        "总投资": total_investment,
        "售价": sale_avg_price if sub_type in ["出售类", "租售结合类"] else 0,
        "租金": rent_start_price if sub_type in ["出租类", "租售结合类"] else 0,
        "土地成本": 0,
        "可售面积占比": (sale_area / total_build_area) if total_build_area and sale_area > 0 else 0,
        "商业面积占比": (comm_area / total_build_area) if total_build_area and comm_area > 0 else 0,
        "住宅稳定期出租率": 0,
        "商业起始租金": comm_rent_start_price
    }

    similar_project_names = []
    if history_df is not None and not history_df.empty:
        try:
            similar_df = find_similar_projects(core_input, history_df, top_n=3)
            if similar_df is not None and not similar_df.empty:
                similar_project_names = similar_df["项目名称"].tolist()
        except:
            similar_project_names = []

    # 3. 表格摘要
    table_digest = build_ai_table_digest(
        project_type=project_type,
        income_df=income_df,
        total_cost_df=total_cost_df,
        loan_df=loan_df,
        profit_df=profit_df,
        cf_df=cf_df,
        tax_df=tax_df,
        rental_cost_df=rental_cost_df
    )

    return {
        "project_type": project_type,
        "sub_type": sub_type,
        "total_build_area": total_build_area,
        "total_investment": total_investment,
        "sale_price": sale_avg_price if sub_type in ["出售类", "租售结合类"] else 0,
        "rent_price": rent_start_price if sub_type in ["出租类", "租售结合类"] else 0,
        "similar_project_names": similar_project_names,
        "total_income": total_income,
        "total_cost": total_cost,
        "total_net_profit": total_net_profit,
        "total_npv_sum": total_npv_sum,
        "irr_value": irr_value,
        "interest_coverage_ratio": interest_coverage_ratio,
        "table_digest": table_digest
    }

def call_kimi_cloud_for_chat(messages, context_text):
    """
    调用 Kimi 云端聊天接口
    返回字符串；失败时返回 None
    """
    #secret_value = get_secret_value("KIMI_API_KEY", "")
    # 注意：这是不安全的做法！用完请改回来或删除密钥
    secret_value = "sk-QlarYFqgZOncmq90xrY9gdSWkgg3jAxmK399R2nW1ZSPj3Qe" 
    if not secret_value:
        set_llm_debug_status(False, "未检测到 KIMI_API_KEY，请先在 Streamlit Secrets 中配置")
        return None

    kimi_chat_url = "https://api.moonshot.cn/v1/chat/completions"

    try:
        recent_messages = messages[-4:] if messages else []

        api_messages = []
        system_prompt = f"""
你是一个安居房/保障房项目财务测算分析助手，你的任务不是泛泛讲财务理论，而是“紧贴当前这张测算表”回答。

回答规则：
1. 必须优先引用当前测算结果中的具体数字，不要只讲泛泛理论；
2. 如果用户问“为什么净现值不高/为什么IRR低/为什么利润差”，要从收入结构、成本结构、现金流时点、融资费用、税金等角度结合数字解释；
3. 如果用户问“怎么优化”，要优先提出对当前模型可落地的参数优化建议，如售价、租金、出租率、车位收入系数、总投资、土地成本、建安成本、借款结构、回款节奏；
4. 不要虚构表格里没有的数据；
5. 回答尽量采用以下格式：
   - 先给结论
   - 再列 2~4 条结合本项目数字的原因
   - 最后给 2~4 条针对性的优化建议
6. 如果用户的问题很短，例如“为什么净现值不高”，你要默认理解为：请结合当前测算表解释，而不是给教材定义；
7. 回答语言简洁、专业，适合汇报场景；
8. 如果是出售类项目，要区分销售收入、商业出租、出租净收益现值、销售税金及附加、开发成本投资；
9. 如果是出租类项目，要区分住宅租金收入、车位收入、经营成本、税金及现金流；
10. 优先分析“影响最大”的项目，不要平均用力。

当前项目测算上下文：
{context_text}
""".strip()

        api_messages.append({
            "role": "system",
            "content": system_prompt
        })

        for i, msg in enumerate(recent_messages):
            role = msg.get("role", "user")
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            if role not in ["user", "assistant"]:
                role = "user"
        
            if role == "user" and i == len(recent_messages) - 1:
                content = f"请严格结合当前测算表中的数字回答这个问题：{content}"
        
            api_messages.append({
                "role": role,
                "content": content
            })

        resp = requests.post(
            kimi_chat_url,
            headers={
                "Authorization": f"Bearer {secret_value}",
                "Content-Type": "application/json"
            },
            json={
                "model": CLOUD_MODEL,
                "messages": api_messages,
                "temperature": 0.3,
                "max_tokens": 1200
            },
            timeout=120
        )

        resp.raise_for_status()
        data = resp.json()

        answer = ""
        choices = data.get("choices", [])
        if choices:
            answer = choices[0].get("message", {}).get("content", "") or ""

        answer = answer.strip()
        if answer:
            set_llm_debug_status(True, f"Kimi云端调用成功：{CLOUD_MODEL}")
            return answer

        set_llm_debug_status(False, f"Kimi云端返回为空：{data}")
        return None

    except Exception as e:
        set_llm_debug_status(False, f"Kimi云端调用失败：{type(e).__name__}: {e}")
        return None

def call_external_llm_for_chat(messages, context_text):
    if LLM_MODE == "cloud":
        if CLOUD_PROVIDER == "kimi":
            return call_kimi_cloud_for_chat(messages, context_text)

        elif CLOUD_PROVIDER == "anthropic":
            if Anthropic is None:
                set_llm_debug_status(False, "未安装 anthropic SDK")
                return None

            try:
                recent_messages = messages[-8:] if messages else []

                llm_messages = []
                for msg in recent_messages:
                    role = msg.get("role", "user")
                    content = str(msg.get("content", "")).strip()
                    if not content:
                        continue
                    if role not in ["user", "assistant"]:
                        role = "user"
                    llm_messages.append({
                        "role": role,
                        "content": content
                    })

                system_prompt = f"""
你是一个安居房/保障房项目财务测算分析助手。

要求：
1. 基于当前测算结果回答用户问题；
2. 优先解释IRR、净现值、利润、成本、现金流、异常指标和优化建议；
3. 不要虚构上下文中不存在的数据；
4. 回答要简洁、专业。

当前项目测算上下文：
{context_text}
""".strip()

                client = Anthropic()

                resp = client.messages.create(
                    model=CLOUD_MODEL,
                    max_tokens=1200,
                    temperature=0.3,
                    system=system_prompt,
                    messages=llm_messages
                )

                if resp and resp.content:
                    parts = []
                    for block in resp.content:
                        text = getattr(block, "text", "")
                        if text:
                            parts.append(text)

                    answer = "\n".join(parts).strip()
                    if answer:
                        set_llm_debug_status(True, f"云端调用成功：{CLOUD_MODEL}")
                        return answer

                set_llm_debug_status(False, "云端模型返回为空")
                return None

            except Exception as e:
                set_llm_debug_status(False, f"云端模型调用失败：{type(e).__name__}: {e}")
                return None

        else:
            set_llm_debug_status(False, f"未知 CLOUD_PROVIDER：{CLOUD_PROVIDER}")
            return None

    elif LLM_MODE == "ollama":
        set_llm_debug_status(False, "当前部署在云端时不建议使用本地Ollama直连")
        return None

    else:
        set_llm_debug_status(False, f"未知 LLM_MODE：{LLM_MODE}")
        return None

def get_loading_text(elapsed):
    texts = [
        "🧠 正在读取测算结果与关键指标…",
        "📊 正在比对收入、成本、利润与现金流…",
        "🔍 正在定位影响IRR/NPV的核心因素…",
        "✍️ 正在生成针对性的解释与优化建议…"
    ]
    idx = int(elapsed // 1.5) % len(texts)
    return f"{texts[idx]} 已等待 {elapsed:.1f} 秒"

def call_external_llm_with_timer(messages, context_text, hard_timeout=20):
    """
    带前端等待提示和计时的大模型调用
    超过 hard_timeout 秒自动回退本地规则回答，避免一直转圈
    """
    status_box = st.empty()
    start_ts = time.time()

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(call_external_llm_for_chat, messages, context_text)

            while not future.done():
                elapsed = time.time() - start_ts

                # 硬超时：直接回退
                if elapsed >= hard_timeout:
                    set_llm_debug_status(False, f"云端调用超时（>{hard_timeout}秒），将回退本地规则回答")
                    status_box.warning(f"⚠️ 云端分析超时，已回退本地规则回答，用时 {elapsed:.1f} 秒")
                    return None

                status_box.info(get_loading_text(elapsed))
                time.sleep(0.2)

            try:
                answer = future.result(timeout=1)
            except Exception as e:
                set_llm_debug_status(False, f"大模型调用异常：{type(e).__name__}: {e}")
                answer = None

            total_elapsed = time.time() - start_ts

        if answer:
            status_box.success(f"✅ 分析完成，用时 {total_elapsed:.1f} 秒")
        else:
            status_box.warning(f"⚠️ 大模型未返回结果，已回退本地规则回答，用时 {total_elapsed:.1f} 秒")

        return answer

    except Exception as e:
        set_llm_debug_status(False, f"计时调用异常：{type(e).__name__}: {e}")
        status_box.warning("⚠️ 大模型调用失败，已回退本地规则回答")
        return None

def render_ai_chat_panel():
    """
    渲染AI对话面板
    """
    st.subheader("💬 AI测算问答")
    debug_status = get_llm_debug_status()
    if debug_status["ok"] is True:
        st.caption(f"✅ {debug_status['message']}")
    elif debug_status["ok"] is False:
        st.caption(f"❌ {debug_status['message']}")
    else:
        st.caption("ℹ️ 当前尚未发起大模型调用")
    if LLM_MODE == "ollama":
        st.caption("当前问答优先使用本地Ollama模型回答，失败时自动回退到本地规则回答。")
    elif LLM_MODE == "cloud":
        st.caption(f"当前问答优先使用云端大模型回答，服务商：{CLOUD_PROVIDER}，模型：{CLOUD_MODEL}，失败时自动回退到本地规则回答。")
    else:
        st.caption("当前未配置有效的大模型模式，问答将使用本地规则回答。")

    if "ai_chat_messages" not in st.session_state:
        st.session_state["ai_chat_messages"] = [
            {"role": "assistant", "content": "你好，我可以基于当前测算结果继续解释项目收益、成本、IRR、净现值、参考项目、异常指标和优化建议。"}
        ]

    for msg in st.session_state["ai_chat_messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_question = st.chat_input("请输入你的问题，例如：为什么这个项目IRR为负？")
    if user_question:
        st.session_state["ai_chat_messages"].append({"role": "user", "content": user_question})

        context_dict = st.session_state.get("ai_result_context", {})
        context_text = build_ai_enhanced_context_text(context_dict)

        # 先尝试外部大模型；如果没有，就回退到本地规则回答
        llm_answer = call_external_llm_with_timer(
            messages=st.session_state["ai_chat_messages"],
            context_text=context_text
        )

        if not llm_answer:
            llm_answer = answer_ai_chat_local(user_question, context_dict)

        st.session_state["ai_chat_messages"].append({"role": "assistant", "content": llm_answer})

        # 关键：标记已有结果，避免聊天导致页面回退
        st.session_state["ai_result_ready"] = True
        save_ai_result_snapshot({
            **get_ai_result_snapshot(),
            "page_key": get_ai_result_snapshot().get("page_key", ""),
            "ai_result_context": st.session_state.get("ai_result_context", {}).copy()
        })
        st.rerun()
        
def build_risk_and_suggestion_text(context_dict):
    """
    根据当前测算结果，生成异常指标解释 + 优化建议
    """
    if not context_dict:
        return {
            "risk_text": "暂无测算结果，无法生成异常指标解释。",
            "suggestion_text": "请先完成一次AI测算。"
        }

    total_income = float(context_dict.get("total_income", 0) or 0)
    total_cost = float(context_dict.get("total_cost", 0) or 0)
    total_net_profit = float(context_dict.get("total_net_profit", 0) or 0)
    total_npv_sum = float(context_dict.get("total_npv_sum", 0) or 0)
    irr_raw = str(context_dict.get("irr_value", "")).replace("%", "").replace(" ", "")
    interest_coverage_ratio = float(context_dict.get("interest_coverage_ratio", 0) or 0)

    try:
        irr_num = float(irr_raw)
    except:
        irr_num = None

    risks = []
    suggestions = []

    # 风险解释
    if total_npv_sum < 0:
        risks.append("净现值为负，说明按当前折现率口径看，项目未来现金流不足以覆盖资金时间价值，整体财务吸引力偏弱。")
    if irr_num is not None and irr_num < 0:
        risks.append("IRR为负，通常意味着项目全周期净现金流回收偏慢，或者前期投入过高、后期收入释放不足。")
    if total_net_profit < 0:
        risks.append("净利润为负，说明在当前收入与成本假设下，项目整体无法实现会计口径盈利。")
    if interest_coverage_ratio < 1:
        risks.append("利息保障倍数低于1，说明项目经营收益对利息支出的覆盖能力较弱，偿债安全边际不足。")
    elif interest_coverage_ratio < 1.5:
        risks.append("利息保障倍数偏低，说明项目偿债能力有一定压力。")

    if total_cost > total_income:
        risks.append("总成本高于总收入，当前模型下项目盈亏平衡尚未实现。")

    if not risks:
        risks.append("当前未发现特别突出的异常指标，整体财务表现处于可接受区间，但仍建议结合实际参数进一步校核。")

    # 优化建议
    if total_npv_sum < 0 or (irr_num is not None and irr_num < 0):
        suggestions.append("可以优先从提升运营收入入手，例如上调可售售价、优化租金水平、提高出租率或提高车位收入系数。")
        suggestions.append("可以重新审视总投资与建设投资节奏，若能压降前期投入或延后部分支出，通常会改善NPV与IRR。")
        suggestions.append("可以重点检查土地成本、建安成本、基础设施费等大额成本参数，若有优化空间，财务结果会明显改善。")

    if interest_coverage_ratio < 1.5:
        suggestions.append("建议优化借款结构，例如降低借款规模、拉长借款期限或降低利率，以改善利息保障能力。")

    suggestions.append("建议对最敏感的参数做情景测算，如售价±5%、租金±5%、总投资±10%、出租率±5%，用于识别关键影响因素。")
    suggestions.append("如需正式决策，建议将AI补齐参数转为可编辑模式，由人工复核后再次测算。")

    return {
        "risk_text": "；".join(risks),
        "suggestion_text": "；".join(suggestions)
    }


def save_ai_result_snapshot(result_dict):
    """
    保存当前测算结果快照，供聊天/刷新后继续展示
    """
    st.session_state["ai_result_snapshot"] = result_dict
    st.session_state["ai_result_ready"] = True


def get_ai_result_snapshot():
    return st.session_state.get("ai_result_snapshot", {})

def has_ai_result_snapshot():
    return st.session_state.get("ai_result_ready", False)

def get_current_page_key(is_ai_mode, selected_project_type):
    """
    生成当前页面唯一标识：
    - AI页固定为 AI_MODE
    - 普通页按项目类型区分
    """
    return "AI_MODE" if is_ai_mode else selected_project_type
def has_result_snapshot_for_current_page(current_page_key):
    """
    只有当快照属于当前页面时，才允许直接回显
    避免从AI页切到普通页时误显示旧结果
    """
    snap = get_ai_result_snapshot()
    if not st.session_state.get("ai_result_ready", False):
        return False
    if not snap:
        return False
    return snap.get("page_key") == current_page_key

def set_llm_debug_status(ok, message):
    st.session_state["llm_debug_ok"] = ok
    st.session_state["llm_debug_message"] = message

def get_llm_debug_status():
    return {
        "ok": st.session_state.get("llm_debug_ok", None),
        "message": st.session_state.get("llm_debug_message", "尚未调用大模型")
    }
    
def get_secret_value(name, default=""):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)

def _round2(x, default=0.0):
    try:
        if pd.isna(x):
            return default
        return round(float(x), 2)
    except:
        return default


def _safe_get_sum(df, col):
    try:
        if df is not None and col in df.columns:
            return _round2(df[col].sum(), 0.0)
    except:
        pass
    return 0.0


def _top_n_dict(d, n=3):
    if not d:
        return []
    items = sorted(d.items(), key=lambda x: abs(x[1]), reverse=True)
    return items[:n]

# ===================== 【最小改动】项目类型配置字典（所有规则统一放这里，新增/改项目只动这里）=====================
PROJECT_CONFIG = {
    # 类型1：出租型(协议出让/合作类等)
    "出租型(协议出让/合作类等)": {
        "extra_inputs": [],  # 单位：元/㎡/月,
        "ui_components": ["rent_basic"],  # 前端(出租基本信息模块显示)
        "calc_rules": {
            # 出租型规则：自动递增还款(还款模式、首期还款率、还款递增率)
            "repay_plan_mode": "auto",
            "first_repay_ratio": 3.0,
            "repay_increase_rate": 4.5
        },
        "show_metrics": []
    },
    # 类型2：出售类(配保房/可售型人才房等)
    "出售类(配保房/可售型人才房等)": {
        "extra_inputs": [],
        "ui_components": ["custom_repay_plan", "sale_and_commercial"],  # 合并成1个标记 #前端(显示自定义还款计划、销售模块)
        "calc_rules": {"repay_plan_mode": "custom"}, #出售型规则:用户自定义还款
        "show_metrics": []
    },
    # 类型3：租售结合类
    "租售结合类": {
        "extra_inputs": [],
        "ui_components": [],
        "calc_rules": {},
        "show_metrics": []
    },
    # 👇 只加这一段
    "🤖 AI智能测算": {
        "extra_inputs": [],
        "ui_components": ["ai_mode"],
        "calc_rules": {"repay_plan_mode": "custom"}
    }
}
# 全局初始化项目类型参数（保留，后面代码要用到）
project_type = list(PROJECT_CONFIG.keys())[0]  #默认展示第一个
extra_params_global = {}  #项目类型独有输入框储存地方

# ===================== 页面配置（优化：更适合手机）=====================
st.set_page_config(page_title="安居房财务测算", page_icon="🏠", layout="centered")
st.title("🏠 安居房财务测算计算器")
st.markdown("---")

# ===================== 【移到最开头】项目类型选择（用户一进来就能选）=====================
st.subheader("📌 项目类型选择")
project_type = st.selectbox("请选择项目类型", list(PROJECT_CONFIG.keys()), index=0)
current_config = PROJECT_CONFIG[project_type]
# 初始化显隐状态（最小改动）
if "show_resi" not in st.session_state: st.session_state["show_resi"] = True
if "show_comm" not in st.session_state: st.session_state["show_comm"] = True
if "show_park" not in st.session_state: st.session_state["show_park"] = True

# 动态生成该项目类型的专属参数（如果配置里有，就自动显示）
extra_params_global = {}
if current_config["extra_inputs"]:
    st.markdown(f"#### {project_type}专属参数")
    for input_info in current_config["extra_inputs"]:
        if input_info["type"] == "number":
            extra_params_global[input_info["name"]] = st.number_input(
                input_info["name"], 
                min_value=input_info["min"], 
                default=input_info["default"], 
                step=input_info["step"]
            )
        elif input_info["type"] == "percent":
            extra_params_global[input_info["name"]] = st.number_input(
                input_info["name"], 
                min_value=input_info["min"], 
                max_value=input_info["max"], 
                default=input_info["default"], 
                step=input_info["step"]
            )
st.markdown("---")

# ===================== 【最终版】AI模式 / 普通模式 彻底分流 =====================
is_ai_mode = "ai_mode" in current_config.get("ui_components", [])
current_page_key = get_current_page_key(is_ai_mode, project_type)
# ===================== 修复：离开AI模式时，清掉AI专属触发状态 =====================
if not is_ai_mode:
    st.session_state["ai_mode_ready"] = False
    st.session_state["ai_calc_trigger"] = False

# 初始化所有测算需要的变量（先给默认值，避免报错）
residential_area, rent_start_price = 0, 0.0
rent_increase_span, rent_increase_rate = 3, 2.0
occupancy_ramp_dict, stable_start, stable_end, occupancy_stable = {}, 0, 0, 0.0
comm_area, comm_rent_start_price = 0, 0.0
park_count, park_rent_start_price, park_income_ratio = 0, 0.0, 0.0
other_income_name, other_income_total = "其他收入", 0.0
manage_coeff, total_build_area = 1.92, 50000
total_investment, loan_annual_rate, loan_total_years = 50000.0, 3.0, 25
land_cost, construction_cost, infra_cost = 0.0, 0.0, 0.0
discount_rate = 8.0
sale_area, sale_avg_price, sale_ramp_dict = 0, 0.0, {}
build_years, operate_years = [], []
house_type = "公租房"
invest_plan_dict, loan_plan_dict, repay_plan_dict = {}, {}, {}

# ===================== 【AI模式：纯核心输入，无任何多余界面】 =====================
# ===================== 【最终修复版】AI模式 =====================
# ===================== 【最终极简修复】AI模式 =====================
# ===================== 【终极一步到位】AI智能测算模式（零报错·全自动）=====================
# ===================== AI模式：核心输入 -> 历史项目匹配 -> 自动补参 -> 触发原测算 =====================
if is_ai_mode:
    st.header("🤖 AI智能测算（按类型动态显示，最多15项）")

    with st.expander("核心指标", expanded=True):
        # -------- 通用9项 --------
        ai_sub_type = st.radio("项目子类型", ["出售类", "出租类", "租售结合类"], horizontal=True)
        total_build_area = st.number_input("总建筑面积（㎡）", min_value=1, value=50000, step=100)
        total_investment = st.number_input("总投资（万元）", min_value=0.0, value=50000.0, step=1000.0)

        build_start = st.number_input("建设期起始年", value=2025, step=1)
        build_end = st.number_input("建设期结束年", value=2026, step=1)
        operate_start = st.number_input("运营起始年", value=2027, step=1)
        operate_end = st.number_input("运营结束年", value=2057, step=1)

        loan_annual_rate = st.number_input("借款年利率（%）", min_value=0.0, max_value=20.0, value=3.0, step=0.1)
        discount_rate = st.number_input("折现率（%）", min_value=0.0, max_value=50.0, value=8.0, step=0.1)

        # 默认值兜底
        land_cost_input = 0.0
        sale_avg_price = 0.0
        resi_rent_start = 0.0
        sale_area_ratio_pct = 0.0
        comm_area_ratio_pct = 0.0
        occupancy_stable_pct = 0.0
        comm_rent_start_price_input = 0.0

        st.markdown("---")
        st.subheader("🎯 类型关键参数")

        # -------- 出售类：5项，合计14项 --------
        if ai_sub_type == "出售类":
            st.caption("当前共 14 项：通用9项 + 出售类关键5项")
            land_cost_input = st.number_input("土地成本（万元）", min_value=0.0, value=float(total_investment) * 0.25, step=100.0)
            sale_avg_price = st.number_input("可售售价（元/㎡）", min_value=0.0, value=10000.0, step=100.0)
            sale_area_ratio_pct = st.number_input("可售面积占比（%）", min_value=0.0, max_value=100.0, value=78.0, step=1.0)
            comm_area_ratio_pct = st.number_input("商业面积占比（%）", min_value=0.0, max_value=100.0, value=8.0, step=1.0)
            comm_rent_start_price_input = st.number_input("商业起始租金（元/㎡/月）", min_value=0.0, value=30.0, step=1.0)

        # -------- 出租类：5项，合计14项 --------
        elif ai_sub_type == "出租类":
            st.caption("当前共 14 项：通用9项 + 出租类关键5项")
            land_cost_input = st.number_input("土地成本（万元）", min_value=0.0, value=float(total_investment) * 0.25, step=100.0)
            resi_rent_start = st.number_input("住宅租金（元/㎡/月）", min_value=0.0, value=19.2, step=0.1)
            occupancy_stable_pct = st.number_input("住宅稳定期出租率（%）", min_value=0.0, max_value=100.0, value=90.0, step=1.0)
            comm_area_ratio_pct = st.number_input("商业面积占比（%）", min_value=0.0, max_value=100.0, value=6.0, step=1.0)
            comm_rent_start_price_input = st.number_input("商业起始租金（元/㎡/月）", min_value=0.0, value=28.0, step=1.0)

        # -------- 租售结合类：6项，合计15项 --------
        else:
            st.caption("当前共 15 项：通用9项 + 租售结合类关键6项")
            land_cost_input = st.number_input("土地成本（万元）", min_value=0.0, value=float(total_investment) * 0.25, step=100.0)
            sale_avg_price = st.number_input("可售售价（元/㎡）", min_value=0.0, value=10000.0, step=100.0)
            resi_rent_start = st.number_input("住宅租金（元/㎡/月）", min_value=0.0, value=19.2, step=0.1)
            sale_area_ratio_pct = st.number_input("可售面积占比（%）", min_value=0.0, max_value=100.0, value=45.0, step=1.0)
            comm_area_ratio_pct = st.number_input("商业面积占比（%）", min_value=0.0, max_value=100.0, value=8.0, step=1.0)
            occupancy_stable_pct = st.number_input("住宅稳定期出租率（%）", min_value=0.0, max_value=100.0, value=90.0, step=1.0)

    if st.button("🤖 AI一键测算", type="primary", use_container_width=True):
        try:
            with st.spinner("正在匹配历史项目并自动补参..."):
                history_df = load_builtin_history_projects()

                build_years_ai = list(range(int(build_start), int(build_end) + 1))
                operate_years_ai = list(range(int(operate_start), int(operate_end) + 1))

                core_input = {
                    "项目子类型": ai_sub_type,
                    "总建筑面积": total_build_area,
                    "总投资": total_investment,
                    "运营期年份": operate_years_ai,
                    "售价": sale_avg_price,
                    "租金": resi_rent_start,
                    # 新增核心字段
                    "土地成本": land_cost_input,
                    "可售面积占比": sale_area_ratio_pct / 100 if sale_area_ratio_pct > 0 else 0,
                    "商业面积占比": comm_area_ratio_pct / 100 if comm_area_ratio_pct > 0 else 0,
                    "住宅稳定期出租率": occupancy_stable_pct / 100 if occupancy_stable_pct > 0 else 0,
                    "商业起始租金": comm_rent_start_price_input,
                    # 便于说明表展示
                    "借款年利率": loan_annual_rate,
                    "折现率": discount_rate
                }
                similar_df = find_similar_projects(core_input, history_df, top_n=3)
                ai_params, ai_msg = ai_fill_indicators(core_input, history_df)

                subtype_to_project_type = {
                    "出售类": "出售类(配保房/可售型人才房等)",
                    "出租类": "出租型(协议出让/合作类等)",
                    "租售结合类": "租售结合类"
                }

                show_resi = ai_sub_type in ["出租类", "租售结合类"]
                show_comm = True
                show_park = True

                st.session_state["ai_mode_ready"] = True
                st.session_state["ai_calc_trigger"] = True
                st.session_state["ai_msg"] = ai_msg
                st.session_state["ai_params"] = ai_params
                st.session_state["ai_core_input"] = core_input
                st.session_state["ai_similar_projects"] = similar_df.to_dict("records") if not similar_df.empty else []
                st.session_state["ai_similar_project_names"] = similar_df["项目名称"].tolist() if not similar_df.empty else []
                st.session_state["ai_base"] = {
                    "project_type": subtype_to_project_type[ai_sub_type],
                    "ai_sub_type": ai_sub_type,
                    "total_build_area": total_build_area,
                    "total_investment": total_investment,
                    "build_years": build_years_ai,
                    "operate_years": operate_years_ai,
                    "operate_start": int(operate_start),
                    "operate_end": int(operate_end),
                    "sale_avg_price": sale_avg_price,
                    "resi_rent_start": resi_rent_start,
                    "loan_annual_rate": loan_annual_rate,
                    "discount_rate": discount_rate,
                    "show_resi": show_resi,
                    "show_comm": show_comm,
                    "show_park": show_park
                }

                st.session_state["debug_ai_clicked"] = True
                st.session_state["debug_ai_time"] = datetime.now().strftime("%H:%M:%S")
                st.rerun()
        except Exception as e:
            st.error(f"AI一键测算触发失败：{e}")
    if st.button("♻️ 清空AI结果并重新填写", use_container_width=True):
        for k in [
        "ai_mode_ready", "ai_calc_trigger", "ai_msg", "ai_params", "ai_base",
        "ai_core_input", "ai_similar_projects", "ai_similar_project_names",
        "ai_result_context", "ai_chat_messages",
        "ai_result_snapshot", "ai_result_ready"
        ]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    # 第一次进入AI页但还没点按钮时，先停止，不往下跑手工模式
    if not st.session_state.get("ai_mode_ready", False):
        st.info("请先填写核心指标后点击“AI一键测算”。")
        st.stop()

    # ========== AI参数已生成：开始回填到原变量，供下面原测算逻辑直接使用 ==========
    ai_p = st.session_state["ai_params"]
    ai_b = st.session_state["ai_base"]

    project_type = ai_b["project_type"]
    current_config = PROJECT_CONFIG[project_type]

    project_name = f"AI测算_{ai_b['ai_sub_type']}_{datetime.now().strftime('%Y%m%d')}"

    build_years = ai_b["build_years"]
    operate_years = ai_b["operate_years"]
    operate_start = ai_b["operate_start"]
    operate_end = ai_b["operate_end"]

    total_build_area = ai_b["total_build_area"]
    total_investment = ai_b["total_investment"]
    sale_avg_price = ai_b["sale_avg_price"]
    loan_annual_rate = ai_b["loan_annual_rate"]
    discount_rate = ai_b["discount_rate"]

    st.session_state["show_resi"] = ai_b["show_resi"]
    st.session_state["show_comm"] = ai_b["show_comm"]
    st.session_state["show_park"] = ai_b["show_park"]

    # 基础变量回填
    residential_area = ai_p["residential_area"]
    rent_start_price = ai_b["resi_rent_start"]
    rent_increase_span = ai_p["rent_increase_span"]
    rent_increase_rate = ai_p["rent_increase_rate"]
    occupancy_ramp_dict = ai_p["occupancy_ramp_dict"]
    stable_start = ai_p["stable_start"]
    stable_end = ai_p["stable_end"]
    occupancy_stable = ai_p["occupancy_stable"]

    comm_area = ai_p["comm_area"]
    comm_rent_start_price = ai_p["comm_rent_start_price"]
    comm_rent_increase_span = ai_p["comm_rent_increase_span"]
    comm_rent_increase_rate = ai_p["comm_rent_increase_rate"]
    comm_occupancy_ramp_dict = {operate_start: 0.7, min(operate_start + 1, operate_end): 0.8}
    comm_stable_start = min(operate_start + 2, operate_end)
    comm_stable_end = operate_end
    comm_occupancy_stable = ai_p["comm_occupancy_stable"]
    comm_rent_stable_start = operate_end

    park_count = int(ai_p["park_count"])
    park_rent_start_price = ai_p["park_rent_start_price"]
    park_income_ratio = ai_p["park_income_ratio"]
    park_occupancy_ramp_dict = {operate_start: 0.7, min(operate_start + 1, operate_end): 0.8}
    park_stable_start = min(operate_start + 2, operate_end)
    park_stable_end = operate_end
    park_occupancy_stable = ai_p["park_occupancy_stable"]

    other_income_name = ai_p["other_income_name"]
    other_income_total = ai_p["other_income_total"]
    manage_coeff = ai_p["manage_coeff"]

    land_cost = ai_p["land_cost"]
    construction_cost = ai_p["construction_cost"]
    infra_cost = ai_p["infra_cost"]
    sale_area = ai_p["sale_area"]
    sale_ramp_dict = ai_p["sale_ramp_dict"]

    # 你原测算里会用到的其他变量，一并兜底
    house_type = "公租房"
    lease_months = 12
    loan_total_years = 25
    first_repay_ratio = 3.0
    repay_increase_rate = 4.5
    land_area = total_build_area // 3
    residential_decoration_cost = total_build_area * 800 / 10000
    other_eng_cost = construction_cost * 0.05
    project_input_tax = construction_cost * 0.09
    land_use_area = total_build_area // 3
    land_area = land_use_area
    land_floor_price = 1000
    dev_cost = total_investment * 0.1
    sale_construction_cost = construction_cost * 0.70
    sale_infra_cost = infra_cost * 0.70
    stamp_tax_rate = 0.0
    comm_custom_increase_list = []

    invest_plan_dict = {y: total_investment / len(build_years) for y in build_years} if build_years else {}
    loan_plan_dict = {y: total_investment * 0.7 / len(build_years) for y in build_years} if build_years else {}
    repay_plan_dict = {}

    st.success("AI参数已生成完成")
    st.caption(st.session_state.get("ai_msg", ""))
    st.success("AI参数已生成并回填完成，正在进入统一测算流程。")

# ===================== 【普通模式：原来的完整手动输入界面】 =====================
else:
    # 这里直接粘贴你原来的「请输入项目数据」的所有代码，和之前完全一样
    # 比如：st.header("📝 请输入项目数据")、各种输入框、expander等
    # 这部分和你之前的代码完全一样，不用改
    st.header("📝 请输入项目数据")
    # --- 粘贴你原来的所有手动输入代码 ---

# ===================== 【测算逻辑：AI模式/普通模式共用，完全不变】 =====================
# 下面直接放你原来的一键测算、收入表、损益表、结果汇总等所有代码
# 这些代码完全不用改，因为上面已经给所有变量赋值了，不管是AI模式还是普通模式，都有值

run_manual_inputs = not (is_ai_mode and st.session_state.get("ai_mode_ready", False))
# ===================== 以下是你原来的所有输入代码，完全不动 =====================
# ===================== 输入区（优化：手机上更易操作）=====================
#st.header("📝 请输入项目数据")
if run_manual_inputs:
    # 定义年份范围（方便后续调整，可选但推荐）
    START_YEAR = 2000
    END_YEAR = 2200
    year_options = list(range(START_YEAR, END_YEAR + 1))  # 生成2000~2200的年份列表


    # 1. 项目基本信息（完整正确版，确保build_years、operate_years全局可访问）
    with st.expander("1. 项目基本信息", expanded=True):
        project_name = st.text_input("项目名称", value="安居XX项目测算（测试）")
        # 【核心修改：仅出租型项目显示房源类型，缩进和上面的project_name完全一致】
        if project_type == "出租型(协议出让/合作类等)":
            house_type = st.radio("房源类型", options=["公租房", "保租房"], index=0, horizontal=True, help="用于匹配装修重置费计算规则")
        else:
            house_type = "公租房"  # 非出租型项目，给固定默认值，不影响计算
        # 建设期年份：原有代码完全不动
        build_years = st.multiselect("建设期年份", options=year_options, default=[2025, 2026])
    
        # ---------------------- 运营期年份区间选择----------------------
        st.subheader("运营期年份（区间选择）")
        # 初始化session_state（仅第一次运行设置默认值/session_state是网页小本本）
        if "operate_start" not in st.session_state: st.session_state["operate_start"] = 2027
        if "operate_end" not in st.session_state: st.session_state["operate_end"] = 2029
    
        # 回调函数：起始年变化时自动修正结束年，防错
        def sync_operate_end():
            if st.session_state["operate_end"] < st.session_state["operate_start"]:
                st.session_state["operate_end"] = st.session_state["operate_start"]
    
        # 输入框一行展示
        col1, col2 = st.columns(2)
        col1.number_input("运营期起始年", min_value=START_YEAR, max_value=END_YEAR, step=1, key="operate_start", on_change=sync_operate_end)
        col2.number_input("运营期结束年", min_value=st.session_state["operate_start"], max_value=END_YEAR, step=1, key="operate_end")
    
        # 【关键】这里的缩进和上面的代码同级，确保operate_years在with块内被定义，外面能访问到
        operate_start = st.session_state["operate_start"]
        operate_end = st.session_state["operate_end"]
        operate_years = list(range(operate_start, operate_end + 1))
    
        # 提示和校验，缩进同级
        st.info(f"✅ 已自动生成运营期年份：{operate_years}")
        if build_years and operate_start < max(build_years):
            st.warning(f"⚠️ 运营期起始年({operate_start})早于建设期最后一年({max(build_years)})，请检查！")

    # 2. 收入计算参数
    with st.expander("2. 收入计算参数", expanded=True):
        lease_months = 12
        sale_area = 0
        # ===================== 【出售类专属·移到最开头】配保房销售设置 ======================
        # 先初始化变量，非出售类自动赋默认值，避免NameError
        sale_area, sale_avg_price, sale_ramp_dict = 0, 0.0, {}
        comm_area, comm_rent_price = 0, 0.0
        dev_cost = 0.0  # 非配售开发成本费默认值
        sale_construction_cost = 0.0  # 配售建安工程费默认值
        sale_infra_cost = 0.0  # 配售基础设施费默认值
        current_config = PROJECT_CONFIG[project_type]
        if "sale_and_commercial" in current_config.get("ui_components", []):
            st.subheader("🏠 配保房销售")
            col_sale1, col_sale2 = st.columns(2)
            sale_area = col_sale1.number_input("销售面积（㎡）", min_value=0, max_value=9999999, value=0, step=100)
            sale_avg_price = col_sale2.number_input("售价（元/㎡）", min_value=0.0, max_value=999999.0, value=0.0, step=100.0)
            sale_ramp_years = st.multiselect("销售年份", operate_years, operate_years[:3])
            if sale_ramp_years:
                cols = st.columns(len(sale_ramp_years))
                for idx, y in enumerate(sale_ramp_years):  #用enmerate自动生成序号
                    sale_ramp_dict[y] = cols[idx].number_input(f"{y}销售率", 0.0, 1.0, 0.3, 0.01)
            st.markdown("---")
       # 出售类专属：有/无收入双按钮（点击“无”全隐藏，点击“有”全显示）
    if ("sale_and_commercial" in current_config.get("ui_components", [])) or ("rent_basic" in current_config.get("ui_components", [])):
        st.markdown("### 🎛️ 收入模块控制")
        # 住宅收入：有/无按钮
        col1, col2 = st.columns(2)
        if col1.button("有住宅收入", key="btn_resi_yes"): st.session_state["show_resi"] = True
        if col2.button("无住宅收入", key="btn_resi_no"): st.session_state["show_resi"] = False
    
        # 商业收入：有/无按钮
        col3, col4 = st.columns(2)
        if col3.button("有商业收入", key="btn_comm_yes"): st.session_state["show_comm"] = True
        if col4.button("无商业收入", key="btn_comm_no"): st.session_state["show_comm"] = False
    
        # 车位收入：有/无按钮
        col5, col6 = st.columns(2)
        if col5.button("有车位收入", key="btn_park_yes"): st.session_state["show_park"] = True
        if col6.button("无车位收入", key="btn_park_no"): st.session_state["show_park"] = False
        st.markdown("---")
        # 基础参数（一行排版）
        if (project_type != "出售类(配保房/可售型人才房等)") or st.session_state["show_resi"]: #（当前选的项目类型不等于出售型）或者（用户刚才点了「有住宅收入」按钮）
            st.subheader("🏠 住宅出租")
            residential_area = st.number_input("住宅面积（㎡）", value=34330, min_value=0)
            rent_start_price = st.number_input("起始租金单价（元/㎡/月）", value=19.2, min_value=0.0, step=0.1)
            # ---------------------- 新增需求①：租金每X年递增Y% ----------------------
            col_rent1, col_rent2 = st.columns(2)
            rent_increase_span = col_rent1.number_input("租金递增跨度（年）", min_value=1, max_value=50, value=3, step=1, help="每过X年租金递增一次")
            rent_increase_rate = col_rent2.number_input("租金递增率（%）", min_value=0.0, max_value=50.0, value=2.0, step=0.1, help="每次递增的百分比")
        
            # ---------------------- 新增需求②：出租率爬坡期+稳定期 ----------------------
            # 先获取运营期年份作为可选范围（联动之前的operate_years）
            if 'operate_years' in locals() and operate_years: #locals()代码花名册
                # 1. 爬坡期设置：让用户选年份，动态生成输入框
                ramp_years = st.multiselect("请选择爬坡期年份（从运营期年份中选）", options=operate_years, default=operate_years[:2] if len(operate_years)>=2 else operate_years)
                # 动态生成爬坡期每年的出租率输入框（一行排版）
                occupancy_ramp_dict = {}
                if ramp_years:
                    col_ramp = st.columns(len(ramp_years))
                    for idx, year in enumerate(ramp_years):
                        occupancy_ramp_dict[year] = col_ramp[idx].number_input(f"{year}年出租率", min_value=0.0, max_value=1.0, value=0.7 if idx==0 else 0.8, step=0.01)
            
                # 2. 稳定期设置：区间选择+固定出租率
                col_stable1, col_stable2, col_stable3 = st.columns(3)
                # 稳定期起始年默认是爬坡期最后一年+1，且≥运营期起始年
                default_stable_start = max(ramp_years) + 1 if ramp_years else operate_years[0]
                stable_start = col_stable1.number_input("稳定期起始年", min_value=operate_start, max_value=operate_end, value=min(operate_start + 2, operate_end))
                # 稳定期结束年默认用运营期结束年，且≥起始年
                stable_end = col_stable2.number_input("稳定期结束年", min_value=stable_start, max_value=operate_years[-1], value=operate_years[-1], step=1)
                # 稳定期固定出租率
                occupancy_stable = col_stable3.number_input("稳定期出租率", min_value=0.0, max_value=1.0, value=0.9, step=0.01)
            else:
                st.warning("⚠️ 请先在「1. 项目基本信息」中设置运营期年份！")
                # 给变量赋默认值，避免NameError
                occupancy_ramp_dict, stable_start, stable_end, occupancy_stable = {}, 0, 0, 0
            
        else:
        # 隐藏时赋默认值（仅5行，避免报错）
            residential_area, rent_start_price = 0, 0.0
            rent_increase_span, rent_increase_rate = 3, 2.0
            occupancy_ramp_dict, stable_start, stable_end, occupancy_stable = {}, 0, 0, 0.0
        
        # ===================== 【出售类专属】商业出租设置（1:1复刻住宅出租）======================
        # 先初始化商业所有变量，非出售类自动赋默认值，避免NameError
        comm_area, comm_rent_start_price = 0, 0.0
        comm_rent_increase_span, comm_rent_increase_rate = 3, 2.0
        comm_occupancy_ramp_dict, comm_stable_start, comm_stable_end, comm_occupancy_stable = {}, 0, 0, 0.9
    
        if ("sale_and_commercial" in current_config.get("ui_components", [])) or ("rent_basic" in current_config.get("ui_components", [])):
            st.markdown("---")
            if st.session_state["show_comm"]:
                st.subheader("🏪 商业出租")
                # 基础参数（和住宅完全一致，仅改名称）
                col_comm1, col_comm2 = st.columns(2)
                comm_area = col_comm1.number_input("商业面积（㎡）", value=0, min_value=0, step=100)
                comm_rent_start_price = col_comm2.number_input("商业起始租金单价（元/㎡/月）", value=0.0, min_value=0.0, step=0.1)
                # 商业租金递增设置（和住宅完全一致，仅改名称）
                # 模式开关（默认不启用）
                comm_use_custom_increase = st.checkbox("启用自定义递增年份（不选则按默认跨度递增）", value=False)
                
                if not comm_use_custom_increase:
                    # 【完全保留原有界面，一丝不动】
                    col_comm_rent1, col_comm_rent2 = st.columns(2)
                    comm_rent_increase_span = col_comm_rent1.number_input("商业租金递增跨度（年）", min_value=1, max_value=50, value=3, step=1, help="每过X年租金递增一次")
                    comm_rent_increase_rate = col_comm_rent2.number_input("商业租金递增率（%）", min_value=0.0, max_value=50.0, value=2.0, step=0.1, help="每次递增的百分比")
                    comm_custom_increase_list = []  # 自定义区间列表留空
                else:
                    # 【自定义模式：每行一组 起始年+结束年+每X年+递增率，无重复key，无重复代码】
                    st.markdown("#### 自定义递增设置")
                    # 用session_state保存行数，刷新不丢失，默认1行
                    if "comm_increase_row_count" not in st.session_state:
                        st.session_state.comm_increase_row_count = 1
                    
                    # 逐行生成输入框（唯一key，彻底解决重复报错）
                    comm_custom_increase_list = []  # 格式：[(起始年, 结束年, 跨度, 递增率), ...]
                    for i in range(st.session_state.comm_increase_row_count):
                        col_start, col_end, col_span, col_rate, col_del = st.columns([2, 2, 2, 3, 1])
                        # 1. 递增起始年（唯一key）
                        inc_start = col_start.selectbox(f"起始年{i+1}", options=operate_years, key=f"comm_inc_start_{i}")
                        # 2. 递增结束年（唯一key，默认和起始年相同）
                        inc_end = col_end.selectbox(f"结束年{i+1}", options=operate_years, index=operate_years.index(inc_start), key=f"comm_inc_end_{i}")
                        # 3. 每X年递增（唯一key）
                        inc_span = col_span.number_input(f"每X年{i+1}", min_value=1, max_value=50, value=1, step=1, key=f"comm_inc_span_{i}")
                        # 4. 对应区间的递增率（唯一key）
                        inc_rate = col_rate.number_input(f"递增率{i+1}（%）", min_value=0.0, max_value=50.0, value=2.0, step=0.1, key=f"comm_inc_rate_{i}")
                        # 5. 删除按钮（唯一key，至少保留1行）
                        if col_del.button("×", key=f"comm_del_{i}", disabled=st.session_state.comm_increase_row_count <= 1):
                            st.session_state.comm_increase_row_count -= 1
                            st.rerun()
                        # 校验：结束年≥起始年，才加入有效列表
                        if inc_end >= inc_start:
                            comm_custom_increase_list.append( (inc_start, inc_end, inc_span, inc_rate) )
                    
                    # 添加行按钮（唯一key）
                    if st.button("+ 添加递增行", key="comm_add_row_btn"):
                        st.session_state.comm_increase_row_count += 1
                        st.rerun()
                    
                    # 原有变量赋默认值，避免报错
                    comm_rent_increase_span = 3
                    comm_rent_increase_rate = 2.0
                
                
                # 商业出租率设置（和住宅完全一致，仅改名称）
                if 'operate_years' in locals() and operate_years:
                    # 商业爬坡期设置
                    comm_ramp_years = st.multiselect("请选择商业爬坡期年份（从运营期年份中选）", options=operate_years, default=operate_years[:2] if len(operate_years)>=2 else operate_years)
                    comm_occupancy_ramp_dict = {}
                    if comm_ramp_years:
                        col_comm_ramp = st.columns(len(comm_ramp_years))
                        for idx, year in enumerate(comm_ramp_years):
                            comm_occupancy_ramp_dict[year] = col_comm_ramp[idx].number_input(f"商业{year}年出租率", min_value=0.0, max_value=1.0, value=0.7 if idx==0 else 0.8, step=0.01)
                
                    # 商业稳定期设置
                    col_comm_stable1, col_comm_stable2, col_comm_stable3 = st.columns(3)
                    comm_default_stable_start = max(comm_ramp_years) + 1 if comm_ramp_years else operate_years[0]
                    comm_stable_start = col_comm_stable1.number_input("商业稳定期起始年", min_value=operate_start, max_value=operate_end, value=min(operate_start + 2, operate_end))
                    comm_stable_end = col_comm_stable2.number_input("商业稳定期结束年", min_value=comm_stable_start, max_value=operate_years[-1], value=operate_years[-1], step=1)
                    comm_occupancy_stable = col_comm_stable3.number_input("商业稳定期出租率", min_value=0.0, max_value=1.0, value=0.9, step=0.01)
                comm_rent_stable_start = st.number_input("商业租金稳定年", min_value=operate_years[0], max_value=operate_years[-1],value=operate_years[0], step=1, help="从该年开始租金不再递增，保持稳定")
            else:
            # 隐藏时赋默认值（仅5行）
                comm_area, comm_rent_start_price = 0, 0.0
                comm_rent_increase_span, comm_rent_increase_rate = 3, 2.0
                comm_occupancy_ramp_dict, comm_stable_start, comm_stable_end, comm_stable_occ = {}, 0, 0, 0.0
            
        # ===================== 出售类专属：税金计算参数（每2个一行） ======================
        if "sale_and_commercial" in current_config.get("ui_components", []):
            st.markdown("---")
            st.subheader("💸 税金及成本计算参数")
            # 第1行：2个参数
            col1, col2 = st.columns(2)
            land_cost = col1.number_input("(非配售)土地成本费（万元）", min_value=0.0, value=0.0, step=10.0)
            construction_cost = col2.number_input("(非配售)建安工程费（万元）", min_value=0.0, value=0.0, step=10.0)
            st.markdown("")  # 换行
        
            # 第2行：2个参数
            col3, col4 = st.columns(2)
            infra_cost = col3.number_input("(非配售)基础设施建设费（万元）", min_value=0.0, value=0.0, step=10.0)
            other_eng_cost = col4.number_input("(非配售)工程建设其他费用（万元）", min_value=0.0, value=0.0, step=10.0)
            st.markdown("")  # 换行
        
            # 第3行：2个参数
            col5, col6 = st.columns(2)
            project_input_tax = col5.number_input("工程进项税（万元）", min_value=0.0, value=0.0, step=0.01, help="直接填入工程类合计进项税，用于增值税迭代计算")
            land_use_area = col6.number_input("用地面积（㎡）", min_value=0, value=0, step=100)
            st.markdown("")  # 换行
    
            # 第4行：公式必填参数（一行2个）
            col7, col8 = st.columns(2)
            land_floor_price = col7.number_input("划拨土地楼面价（元/㎡）", min_value=0.0, value=0.0, step=10.0, help="配保房地价抵减计算用")
            dev_cost = col8.number_input("(非配售)开发成本费（万元）", min_value=0.0, value=0.0, step=10.0, help="非配售部分开发成本，用于累计开发成本计算")
            # 印花税率固定默认0‰，无需用户输入，需要时再用
    
            # 第5行：配售专属参数（一行2个）
            col9, col10 = st.columns(2)
            sale_construction_cost = col9.number_input("(配售)建安工程费（万元）", min_value=0.0, value=0.0, step=10.0, help="配售部分建安工程费，用于增值税进项税计算")
            sale_infra_cost = col10.number_input("(配售)基础设施费（万元）", min_value=0.0, value=0.0, step=10.0, help="配售部分基础设施费，用于增值税进项税计算")
            stamp_tax_rate = 0 / 1000  # 固定0.5‰，转成小数
    
            # 第4行：新增工程进项税（单独一行）
            #plot_ratio_area = col5.number_input("计容建筑面积（㎡）", min_value=1, value=1, step=1, help="用于进项税计算，最小值1避免除0错误")
            #st.markdown("")  # 换行
        
        # ---------------------- 新增：车位收入（逻辑同住宅，仅加特有参数）----------------------
        st.markdown("---")
        if (project_type != "出售类(配保房/可售型人才房等)") or st.session_state["show_park"]:
            st.subheader("🚗 车位收入")
            col_park1, col_park2, col_park3 = st.columns(3)
            park_count = col_park1.number_input("车位个数", min_value=0, value=500, step=1)
            park_rent_start_price = col_park2.number_input("车位起始租金单价（元/个/月）", min_value=0.0, value=300.0, step=10.0)
            park_income_ratio = col_park3.number_input("车位实际收入系数", min_value=0.0, max_value=1.0, value=0.5, step=0.01, help="比如50%填0.5")
             # ---------------------- 车位出租率设置（爬坡期+稳定期，缩进完全匹配）----------------------
            if 'operate_years' in locals() and operate_years:
                # 车位爬坡期设置
                park_ramp_years = st.multiselect("请选择车位爬坡期年份（从运营期年份中选）", options=operate_years, default=operate_years[:2] if len(operate_years)>=2 else operate_years)
                park_occupancy_ramp_dict = {}
                if park_ramp_years:
                    col_park_ramp = st.columns(len(park_ramp_years))
                    for idx, year in enumerate(park_ramp_years):
                        park_occupancy_ramp_dict[year] = col_park_ramp[idx].number_input(f"车位{year}年出租率", min_value=0.0, max_value=1.0, value=0.7 if idx==0 else 0.8, step=0.01)
            
                # 车位稳定期设置
                col_park_stable1, col_park_stable2, col_park_stable3 = st.columns(3)
                park_default_stable_start = max(park_ramp_years) + 1 if park_ramp_years else operate_years[0]
                # 找到车位的那行number_input，同样给value加个min兜底
                park_stable_start = col_park_stable1.number_input("车位稳定期起始年", min_value=operate_start, max_value=operate_end, value=min(operate_start + 2, operate_end))
                park_stable_end = col_park_stable2.number_input("车位稳定期结束年", min_value=park_stable_start, max_value=operate_years[-1], value=operate_years[-1], step=1)
                park_occupancy_stable = col_park_stable3.number_input("车位稳定期出租率", min_value=0.0, max_value=1.0, value=0.9, step=0.01)
            else:
                st.warning("⚠️ 请先在「1. 项目基本信息」中设置运营期年份！")
                park_occupancy_ramp_dict, park_stable_start, park_stable_end, park_occupancy_stable = {}, 0, 0, 0
        
        else:
        # 隐藏时赋默认值（仅5行）
            park_count, park_rent_start_price, park_income_ratio = 0, 0.0, 0.0
            park_occupancy_ramp_dict, park_stable_start, park_stable_end, park_stable_occ = {}, 0, 0, 0.0
        
       
        
        # ---------------------- 其他收入设置（自定义名称+仅首年计入）----------------------
        st.markdown("---")
        st.subheader("📦 其他收入设置")
        col_other1, col_other2 = st.columns(2)
        other_income_name = col_other1.text_input("其他收入名称", value="其他收入")
        other_income_total = col_other2.number_input(f"{other_income_name}总额（万元）", min_value=0.0, value=0.0, step=10.0)
    
       
    st.markdown("---")
    
    # 3. 总成本费用参数
    with st.expander("3. 总成本费用参数", expanded=True):
        # 【一行判断出售类模式】
        is_sale_mode = "sale_and_commercial" in current_config.get("ui_components", [])
        # 【一行给隐藏参数赋默认值，彻底避免未定义报错】
        manage_coeff, total_build_area, residential_decoration_cost, dev_cost_plan_dict = 1.92, 50000, 5000.0, {}
    
        # 非出售类：显示完整经营成本参数（原逻辑完全不动）
        if not is_sale_mode:
            st.subheader("💰 经营成本核心参数")
            col_cost1, col_cost2, col_cost3, col_cost4 = st.columns(4)
            manage_coeff = col_cost1.number_input("管理系数", min_value=0.0, value=1.92, step=0.01, help="1.92×区域系数")
            total_build_area = col_cost2.number_input("总建筑面积（㎡）", min_value=0, value=50000, step=100)
            residential_decoration_cost = col_cost3.number_input("住宅精装修工程费（万元）", min_value=0.0, value=5000.0, step=100.0)
            total_investment = col_cost4.number_input("总投资（万元）", min_value=0.0, value=50000.0, step=1000.0)
        # 出售类：仅显示总投资+开发成本投资计划，自动隐藏3个不需要的参数
        else:
            st.subheader("💰 开发成本核心参数")
            total_investment = st.number_input("总投资（万元）", min_value=0.0, value=50000.0, step=1000.0)
            # 【修复后代码，仅改这一段】
            st.markdown("#### 开发成本投资计划")
            dev_cost_years = st.multiselect("请选择有开发成本投资的年份", options=sorted(list(set(build_years + operate_years))), default=build_years if build_years else [], key="dev_cost_years")
            dev_cost_plan_dict = {}
            if dev_cost_years:
                col_dev_cost = st.columns(len(dev_cost_years))  # 仅创建1次横向列，和银行借款完全一致
                for idx, year in enumerate(dev_cost_years):
                    dev_cost_plan_dict[year] = col_dev_cost[idx].number_input(f"{year}年投资额（万元）", min_value=0.0, value=0.0, step=100.0, key=f"dev_cost_{year}")
        # ---------------------- 【原代码完全不动】银行借款与还本付息参数 ----------------------
        st.markdown("---")
        st.subheader("🏦 银行借款与还本付息参数")
        # 基础参数
        col_loan1, col_loan2 = st.columns(2)
        loan_annual_rate = col_loan1.number_input("借款年利率（%）", min_value=0.0, max_value=20.0, value=3.0, step=0.1)
        loan_total_years = col_loan2.number_input("借款总年限（年）", min_value=1, max_value=100, value=25, step=1, help="借款的总期限，用于计算利息保障倍数的借款期范围")
        # 固定还款规则参数，无需用户修改
        first_repay_ratio = 3.0
        repay_increase_rate = 4.5
    
        # 银行借款计划（动态输入，和出租率操作逻辑一致）
        st.markdown("#### 银行借款计划")
        loan_available_years = sorted(list(set(build_years + operate_years)))
        loan_years = st.multiselect("请选择有借款的年份", options=loan_available_years, default=build_years if build_years else [])
        loan_plan_dict = {}
        if loan_years:
            col_loan_year = st.columns(len(loan_years))
            for idx, year in enumerate(loan_years):
                loan_plan_dict[year] = col_loan_year[idx].number_input(f"{year}年借款额（万元）", min_value=0.0, value=0.0, step=100.0)
        # =====================出售型增加还款计划======================
        repay_plan_dict = {}
        current_config = PROJECT_CONFIG[project_type]
        if "custom_repay_plan" in current_config.get("ui_components", []):
            st.markdown("#### 银行还款计划")
            repay_available_years = operate_years
            repay_years = st.multiselect("请选择有还款的年份", options=repay_available_years, default=operate_years[:3] if len(operate_years)>=loan_total_years else operate_years)
            if repay_years:
                col_repay_year = st.columns(len(repay_years))
                for idx, year in enumerate(repay_years):
                    repay_plan_dict[year] = col_repay_year[idx].number_input(f"{year}年还款本金（万元）", min_value=0.0, value=0.0, step=100.0)
    
    # 4. 税金及其附加参数（出售类不显示）
    if project_type != "出售类(配保房/可售型人才房等)":
        with st.expander("4. 税金及其附加参数", expanded=True):
            st.subheader("📝 税金核心参数")
            col_tax1, col_tax2 = st.columns(2)
            land_area = col_tax1.number_input("用地面积（㎡）", min_value=0, value=10000, step=100)
            construction_cost = col_tax2.number_input("建安工程费（万元）", min_value=0.0, value=30000.0, step=1000.0)
    else:
        # 给默认值，防止后面计算报错
        land_area = 0
    
    # 5. 全投资现金流量表参数
    with st.expander("5. 全投资现金流量表参数", expanded=True):
        st.subheader("📊 现金流量表核心参数")
        # 折现率输入
        discount_rate = st.number_input("折现率（%）", min_value=0.0, max_value=50.0, value=8.0, step=0.1)
        # 建设投资计划（和银行借款计划模式完全一致，选年份动态生成输入框）
        st.markdown("#### 建设投资计划")
        invest_available_years = sorted(list(set(build_years + operate_years)))
        invest_years = st.multiselect("请选择有建设投资的年份", options=invest_available_years, default=build_years if build_years else [])
        # 动态生成每年建设投资输入框
        invest_plan_dict = {}
        if invest_years:
            col_invest_year = st.columns(len(invest_years))
            for idx, year in enumerate(invest_years):
                invest_plan_dict[year] = col_invest_year[idx].number_input(f"{year}年建设投资额（万元）", min_value=0.0, value=0.0, step=100.0)
    
    # 6. 一键测算按钮
# ===================== 6. 一键测算按钮（AI模式隐藏手动按钮） =====================
if is_ai_mode:
    calc_button = st.session_state.get("ai_calc_trigger", False)
else:
    calc_button = st.button("🔽 一键开始测算", type="primary", use_container_width=True)

# ===================== 核心测算函数=====================
def generate_year_list(build_yrs, operate_yrs):
    all_years = sorted(list(set(build_yrs + operate_yrs)))
    month_dict = {year: 0 if year in build_yrs else 12 for year in all_years} #建设年算0/否则算12
    is_operate = {year: year in operate_yrs for year in all_years} #判断运营年
    return all_years, month_dict, is_operate

def calc_income(all_years, month_dict, is_operate, area, price, increase_span, increase_rate, occupancy_ramp_dict, stable_start, stable_end, stable_occ, park_count, park_price, park_ratio, park_occupancy_ramp_dict, park_stable_start, park_stable_end, park_stable_occ, other_name, other_total):
    income_df = pd.DataFrame(index=all_years) #建一张按年份排列表
    resi_occupancy, resi_rent_price, park_occupancy, park_rent_price = {}, {}, {}, {} #住宅、车位出租率及单价
    operate_year_list = [y for y in all_years if is_operate[y]] #只算运营期
    
    # 1. 计算住宅每年出租率（涨/稳定/0）
    for year in operate_year_list:
        if year in occupancy_ramp_dict: resi_occupancy[year] = occupancy_ramp_dict[year]
        elif stable_start <= year <= stable_end: resi_occupancy[year] = stable_occ
        else: resi_occupancy[year] = 0.0
    
    # 2. 计算车位每年出租率（涨/稳定/0）
    for year in operate_year_list:
        if year in park_occupancy_ramp_dict: park_occupancy[year] = park_occupancy_ramp_dict[year]
        elif park_stable_start <= year <= park_stable_end: park_occupancy[year] = park_stable_occ
        else: park_occupancy[year] = 0.0
    
    # 3. 计算租金单价（住宅正常递增，车位固定起始价不递增）
    # 住宅租金：原有递增逻辑完全不变
    for idx, year in enumerate(operate_year_list):
        increase_times = idx // increase_span
        resi_rent_price[year] = price * (1 + increase_rate / 100) ** increase_times
    # 车位租金：固定起始价，全程不递增
    for year in operate_year_list:
        park_rent_price[year] = park_price
    
    # 4. 计算每年收入
    for year in all_years:
        if not is_operate[year]:
            income_df.loc[year, "住宅租金收入(万元)"] = 0
            income_df.loc[year, "车位收入(万元)"] = 0
            income_df.loc[year, f"{other_name}(万元)"] = 0
            #income_df.loc[year, "计算过程说明"] = "建设期，无收入"
        else:
            # 住宅收入
            resi_occ, resi_months, resi_rent = resi_occupancy[year], month_dict[year], resi_rent_price[year]
            resi_year_rent = area * resi_rent * resi_occ * resi_months / 10000
            # 车位收入
            park_occ, park_months, park_rent = park_occupancy[year], month_dict[year], park_rent_price[year]
            park_year_rent = park_count * park_rent * park_occ * park_months * park_ratio / 10000
            # 其他收入：仅计入运营期第一年，其他年份为0
            other_year_rent = other_total if year == operate_year_list[0] else 0
            
            # 填入表格
            #income_df.loc[year, "住宅租金单价(元/㎡/月)"] = round(resi_rent, 2)
            #income_df.loc[year, "住宅出租率"] = round(resi_occ, 4)
            income_df.loc[year, "住宅租金收入(万元)"] = round(resi_year_rent, 4)
            #income_df.loc[year, "车位租金单价(元/个/月)"] = round(park_rent, 2)
            #income_df.loc[year, "车位出租率"] = round(park_occ, 4)
            income_df.loc[year, "车位收入(万元)"] = round(park_year_rent, 4)
            income_df.loc[year, f"{other_name}(万元)"] = round(other_year_rent, 4)
            #income_df.loc[year, "计算过程说明"] = f"住宅:{area}×{round(resi_rent,2)}×{round(resi_occ,4)}×{resi_months}/10000 + 车位:{park_count}×{round(park_rent,2)}×{round(park_occ,4)}×{park_months}×{park_ratio}/10000 + {other_name}:{round(other_year_rent,4)}"
    
    # 总收入汇总(表格计算)
    income_df["总收入(万元)"] = income_df["住宅租金收入(万元)"] + income_df["车位收入(万元)"] + income_df[f"{other_name}(万元)"]
    return income_df, resi_occupancy, resi_rent_price, park_occupancy, park_rent_price

# ===================== 新增：(出售型)的出租情况表（营运成本）计算函数 ======================
#(备注防忘)年份列表all_years，建设运营期判断is_operate，运营期年份列表operate_year_list，商业面积comm_area，商业起始租金comm_rent_start_price，商业租金递增跨度comm_rent_increase_span，爬坡期每年的商业出租率字典comm_occupancy_ramp_dict
#商业稳定期起始年comm_stable_start，商业稳定期结束年comm_stable_end，商业稳定期固定出租率comm_occupancy_stable，车位个数park_count，土地成本land_cost，建安工程费construction_cost，基础设施建设费infra_cost，工程建设其他费用other_eng_cost
#用地面积land_use_area，租赁月数lease_months，计容建筑面积plot_ratio_area
def calc_rental_operation_table(all_years, is_operate, operate_year_list, comm_area, comm_rent_start_price, comm_rent_increase_span, comm_rent_increase_rate, comm_occupancy_ramp_dict, comm_stable_start, comm_stable_end, comm_occupancy_stable, park_count, land_cost, construction_cost, infra_cost, other_eng_cost,land_use_area, lease_months,project_input_tax=0.0,comm_custom_increase_list=[], comm_first_increase_year=2):
    """计算出租营运成本明细表（出租情况表），复用现有参数，最小改动"""
    rental_table = pd.DataFrame(index=all_years)
    # （1）. 预计算商业出租率、租金单价（复用住宅/车位的逻辑）
    comm_occupancy, comm_rent_price, comm_rental_income = {}, {}, {} #创造空字典储存商业出租率、单价、收入
    remaining_input = 0 #增值税的2个临时变量
    total_input_tax_calc = 0
    n = 0  # 【仅新增这1行】现值计算的年份序号，从0开始
    for year in operate_year_list:
        # 商业出租率（爬坡期+稳定期）
        if year in comm_occupancy_ramp_dict: comm_occupancy[year] = comm_occupancy_ramp_dict[year] #爬坡期出租率
        elif comm_stable_start <= year <= comm_stable_end: comm_occupancy[year] = comm_occupancy_stable #稳定期出租率
        else: comm_occupancy[year] = 0.0 #防错
        # 商业租金单价（递增逻辑）设置一个让人填稳定的年份判断(总不能一直涨把是不)→没有就默认最后一年
    if comm_rent_stable_start in operate_year_list:
        stable_index = operate_year_list.index(comm_rent_stable_start)
    else:
        stable_index = len(operate_year_list) - 1  # 默认最后一年
    
    # 【修复：租金计算逻辑，先算完所有年份，无嵌套循环，完美匹配需求】
    comm_rent_price = {}
    if comm_custom_increase_list:
        # 自定义区间模式：区间内按「每X年」递增，一次性算完
        current_price = comm_rent_start_price
        # 按运营年份顺序逐年计算
        for calc_year in sorted(operate_year_list):
            # 遍历所有区间，判断当年是否需要递增
            for (start_year, end_year, span, rate) in comm_custom_increase_list:
                if start_year <= calc_year <= end_year:
                    # 核心逻辑：(当年 - 起始年) 能被 跨度 整除，才递增
                    if (calc_year - start_year) % span == 0:
                        current_price *= (1 + rate / 100)
            # 存入当年租金
            comm_rent_price[calc_year] = current_price
    else:
        # 固定规则模式：原有逻辑一丝不动，完全兼容
        for year in operate_year_list:
            year_index = operate_year_list.index(year)
            effective_index = min(year_index, stable_index)
            increase_times = (effective_index + 1) // comm_rent_increase_span
            comm_rent_price[year] = comm_rent_start_price * (1 + comm_rent_increase_rate / 100) ** increase_times
            
    # ===================== 【仅新增】预循环算全周期累计（不填表，不影响其他） ======================
    total_manage_ins, total_vacancy = 0, 0
    for year in operate_year_list:
        occ = comm_occupancy[year] if year in comm_occupancy else 0.0
        cr_price = comm_rent_price[year] if year in comm_rent_price else 0.0
        comm_income = comm_area * cr_price * occ * lease_months / 10000
        total_manage_ins += comm_income * 0.08 + (comm_area * 1.86) / 10000
        total_vacancy += (comm_area * (1 - occ) * 8 * 12 ) / 10000
    total_input_tax_calc = (total_manage_ins * (0.06 / 1.06)) + (total_vacancy * (0.09 / 1.09)) + project_input_tax
    remaining_input = total_input_tax_calc
    # ===================== 预循环结束，下面原代码完全不动 ======================
    
    # （2）. 逐年份计算各项成本/税费
    for year in all_years:
        if not is_operate[year]:  # 建设期：各项为0
            rental_table.loc[year, ["商业出租率", "商业出租收入(万元)", "房产税1(万元)", "房产税2(万元)", 
                                   "运营管理费用（商业）(万元)", "运营管理费用（停车场）(万元)", "物业专项维修金(万元)", 
                                   "维修费用(万元)", "空置物业服务费(万元)", "保险费用(万元)", "土地使用税(万元)", 
                                   "出租营运成本合计(万元)","销项税(万元)","进项税(万元)","增值税(一般计税)(万元)", "增值税附加(万元)", "印花税(万元)", "出租经营税金合计(万元)"]] = 0.0
            # 仅新增这2行（初始化累计缓存）
            if 'cum_vat' not in locals(): cum_vat, cum_rent = [], []
            cum_vat.append(0.0); cum_rent.append(0.0) #累计列表中加0，保持长度一致
            continue
        
        # 运营期核心参数
        occ = comm_occupancy[year] #该年出租率
        cr_price = comm_rent_price[year] #该年出租单价
        # 🚨 新增：出租率为0 → 本年不发生经营（为了匹配乌坭浪那项目,刚运营1年就涨价了晕）
        comm_income = comm_area * cr_price * occ * lease_months / 10000  # 该年商业出租收入（万元）
        
        # 按公式计算各项成本（严格匹配需求，单位统一为万元）
        tax1 = comm_income * (0.12 / 1.09)  # 房产税1
        tax2_base = land_cost + construction_cost + infra_cost + other_eng_cost + construction_cost * 0.02 * comm_area/(sale_area+comm_area) if (sale_area+comm_area)!=0 else 0
        tax2 = tax2_base * 0.7 * 0.012 * (1 - occ)  # 房产税2（防除0）
        manage_comm = comm_income * 0.08  # 运营管理费（商业）
        manage_park = park_count * 80 * 12 / 10000  # 运营管理费（停车场）
        property_fund = (comm_area * lease_months * 0.25) / 10000  # 物业专项维修金
        repair_fee = comm_income * 0.02  # 维修费用
        vacancy_service = (comm_area * (1 - occ) * 8 * 12 ) / 10000  # 空置物业服务费 为啥表格×0.88/0.98搞不懂？
        insurance_fee = (comm_area * 1.86) / 10000  # 保险费用
        land_tax = (land_use_area * (comm_area/(sale_area+comm_area) if (sale_area+comm_area)!=0 else 0) * 3) / 10000 #土地使用税
        total_cost = tax1 + tax2 + manage_comm + manage_park + property_fund + repair_fee + vacancy_service + insurance_fee + land_tax  # 成本合计

        # ===================== 新增：出租经营税金计算逻辑 ======================
        # 1. 首次循环时计算全周期进项税合计（仅算1次）
        # 2. 单年销项税（严格按你的公式：单年租金×9%/(1+9%)）
        output_tax = comm_income * (0.09 / 1.09) if comm_income > 0 else 0.0
        input_before = remaining_input
        vat = max(output_tax - input_before, 0.0)
        remaining_input = max(input_before - output_tax, 0.0)
        # 4. 增值税附加：当年的增值税×12%
        cum_vat.append(vat) #累加函数
        vat_surcharge = vat * 0.12
        # 5. 印花税：当年的租金收入×0.05%
        cum_rent.append(comm_income)
        stamp_tax = comm_income * 0.0005
        # 6. 出租经营税金合计
        total_rental_tax = vat + vat_surcharge + stamp_tax
        # ===================== 计算逻辑结束 ======================
        
        
        # 填入表格（保留4位小数，和原有风格一致）
        rental_table.loc[year, "商业出租率"] = round(occ, 4)
        rental_table.loc[year, "商业出租收入(万元)"] = round(comm_income, 4)
        rental_table.loc[year, "房产税1(万元)"] = round(tax1, 4)
        rental_table.loc[year, "房产税2(万元)"] = round(tax2, 4)
        rental_table.loc[year, "运营管理费用（商业）(万元)"] = round(manage_comm, 4)
        rental_table.loc[year, "运营管理费用（停车场）(万元)"] = round(manage_park, 4)
        rental_table.loc[year, "物业专项维修金(万元)"] = round(property_fund, 4)
        rental_table.loc[year, "维修费用(万元)"] = round(repair_fee, 4)
        rental_table.loc[year, "空置物业服务费(万元)"] = round(vacancy_service, 4)
        rental_table.loc[year, "保险费用(万元)"] = round(insurance_fee, 4)
        rental_table.loc[year, "土地使用税(万元)"] = round(land_tax, 4)
        rental_table.loc[year, "出租营运成本合计(万元)"] = round(total_cost, 4)
        # ===================== 新增：填入税金列 ======================
        rental_table.loc[year, "销项税(万元)"] = round(output_tax, 4)
        rental_table.loc[year, "进项税(万元)"] = round(input_before, 4)
        rental_table.loc[year, "增值税(一般计税)(万元)"] = round(vat, 4)
        rental_table.loc[year, "增值税附加(万元)"] = round(vat_surcharge, 4)
        rental_table.loc[year, "印花税(万元)"] = round(stamp_tax, 4)
        rental_table.loc[year, "出租经营税金合计(万元)"] = round(total_rental_tax, 4)
        # 【新增】出租净收入=商业出租收入-出租营运成本合计-出租经营税金合计
        net_rental_income = rental_table.loc[year, "商业出租收入(万元)"] - rental_table.loc[year, "出租营运成本合计(万元)"] - rental_table.loc[year, "出租经营税金合计(万元)"]
        rental_table.loc[year, "出租净收入(万元)"] = round(net_rental_income, 4)

        pv_net_rental = net_rental_income / ((1 + 0.035) ** n)
        rental_table.loc[year, "出租净收益现值(万元)"] = round(pv_net_rental, 4)
        n += 1  # 年份序号每年+1

        if "销项税(万元)" not in rental_table.columns: rental_table["销项税(万元)"] = 0.0
        rental_table["销项税(万元)"] = rental_table["销项税(万元)"].fillna(0.0)
    
        # 兜底2：进项税列先初始化，避免赋值报错
        if "进项税(万元)" not in rental_table.columns: rental_table["进项税(万元)"] = 0.0
    
        # 进项税迭代
        temp_remaining = total_input_tax_calc
        for year in all_years:
            rental_table.loc[year, "进项税(万元)"] = round(temp_remaining, 4)
            temp_remaining = max(temp_remaining - rental_table.loc[year, "销项税(万元)"], 0.0)
        # ===================== 结束 ======================
        
    return rental_table
  
# ===================== 经营成本测算函数（原calc_cost，适配新命名）=====================
def calc_operating_cost(all_years, month_dict, is_operate, resi_area, resi_occupancy, resi_rent_price, park_income_list, total_build_area, manage_coeff, decoration_cost, house_type, total_investment, operate_year_list):
    operating_cost_df = pd.DataFrame(index=all_years)
    operate_years_count = len(operate_year_list)
    # 运营年份序号：key=年份，value=运营第几年（1、2、3...）
    operate_year_index = {year: idx+1 for idx, year in enumerate(operate_year_list)}
    max_operate_year_num = max(operate_year_index.values())  # 运营期总年数
    
    # 装修重置费计算（原有逻辑完全不变）
    single_reset_total = decoration_cost * 0.7
    reset_period = 20 if house_type == "公租房" else 10
    reset_year_nums = list(range(reset_period, max_operate_year_num + 1, reset_period))
    decoration_reset_dict = {year: 0 for year in operate_year_list}

    for reset_year_num in reset_year_nums:
        start_share_num = reset_year_num
        end_share_num = min(reset_year_num + 9, max_operate_year_num)
        share_year_count = end_share_num - start_share_num + 1
        year_share_amount = single_reset_total / share_year_count if share_year_count > 0 else 0
        for year, year_num in operate_year_index.items():
            if start_share_num <= year_num <= end_share_num:
                decoration_reset_dict[year] += year_share_amount

    # 循环计算每年各项经营成本
    for year in all_years:
        if not is_operate[year]:
            # 建设期无经营成本
            operating_cost_df.loc[year, "管理费用(住房)(万元)"] = 0
            operating_cost_df.loc[year, "管理费用(停车位)(万元)"] = 0
            operating_cost_df.loc[year, "保险费(万元)"] = 0
            operating_cost_df.loc[year, "维修费用(万元)"] = 0
            operating_cost_df.loc[year, "日常物业维修基金(万元)"] = 0
            operating_cost_df.loc[year, "空置期物业管理费(万元)"] = 0
            operating_cost_df.loc[year, "装修重置费(万元)"] = 0
            operating_cost_df.loc[year, "折旧摊销(万元)"] = 0
            operating_cost_df.loc[year, "经营成本(万元)"] = 0
        else:
            # 运营期基础参数
            occ = resi_occupancy.get(year, 0)
            months = month_dict[year]
            resi_rent = resi_rent_price.get(year, 0)
            park_income = park_income_list.get(year, 0)
            
            # 各项经营成本（原有逻辑完全不变）
            manage_house = resi_area * occ * 12 * manage_coeff / 10000
            manage_park = park_income * 0.4
            insurance = total_build_area * 0.3 / 10000
            repair = (resi_area * resi_rent * occ * months / 10000) * 0.02
            fund = resi_area * occ * months * 0.25 / 10000
            vacancy = resi_area * (1 - occ) * months * 3.9 / 10000
            decoration_reset = decoration_reset_dict[year]
            depreciation = total_investment * (1 - 0.2) / 50 if operate_year_index[year] <= 50 else 0
            
            # 填入表格
            operating_cost_df.loc[year, "管理费用(住房)(万元)"] = round(manage_house, 4)
            operating_cost_df.loc[year, "管理费用(停车位)(万元)"] = round(manage_park, 4)
            operating_cost_df.loc[year, "保险费(万元)"] = round(insurance, 4)
            operating_cost_df.loc[year, "维修费用(万元)"] = round(repair, 4)
            operating_cost_df.loc[year, "日常物业维修基金(万元)"] = round(fund, 4)
            operating_cost_df.loc[year, "空置期物业管理费(万元)"] = round(vacancy, 4)
            operating_cost_df.loc[year, "装修重置费(万元)"] = round(decoration_reset, 4)
            operating_cost_df.loc[year, "折旧摊销(万元)"] = round(depreciation, 4)
            # 经营成本合计
            total_operating_cost = manage_house + manage_park + insurance + repair + fund + vacancy + decoration_reset + depreciation
            operating_cost_df.loc[year, "经营成本(万元)"] = round(total_operating_cost, 4)
    
    return operating_cost_df

# ===================== 新增：还本付息测算函数（严格匹配迭代规则）=====================
def calc_loan_repayment(all_years, operate_start_year, loan_plan_dict, annual_rate, first_repay_ratio, repay_increase_rate, loan_total_years, custom_repay_plan=None, project_config=None):
    """
    测算还本付息明细，返回：
    1. loan_df：还本付息表完整明细
    2. financial_cost_dict：每年的财务费用（本期付息额，用于总成本计算）
    """
    loan_df = pd.DataFrame(index=all_years)
    rate = annual_rate / 100  # 转成小数计算
    first_repay_rate = first_repay_ratio / 100
    increase_rate = repay_increase_rate / 100
    
    total_loan = sum(loan_plan_dict.values())  # 借款总额
    # 一行搞定：计算借款期首尾年份，限制迭代周期
    first_loan_year = min(loan_plan_dict.keys()) if loan_plan_dict else min(all_years); last_loan_year = first_loan_year + loan_total_years - 1
    end_loan_last = 0  # 上一年期末借款余额，迭代初始值
    last_repay_principal = 0  # 上一年的还本额，用于递增计算
    is_operate_start = False  # 标记是否进入运营期
    repay_principal_plan = {}
    # ===================== 【最小改动】仅替换预计算逻辑 ======================
    # ===================== 【修复报错】预计算还本计划 ======================
    calc_rules = project_config.get("calc_rules", {}) if project_config else {}
    if calc_rules.get("repay_plan_mode") == "custom" and custom_repay_plan:
        for year in all_years: repay_principal_plan[year] = custom_repay_plan.get(year, 0.0) if year <= last_loan_year else 0.0
    else:
        for year in all_years:
            if year >= operate_start_year and year <= last_loan_year:
                if not is_operate_start: repay_principal, is_operate_start = total_loan * first_repay_rate, True
                else: repay_principal = last_repay_principal * (1 + increase_rate)
                repay_principal_plan[year], last_repay_principal = repay_principal, repay_principal
            else: repay_principal_plan[year] = 0.0

    # 第二步：迭代计算每年的还本付息数据（严格按你给的公式）
    for year in all_years:
        # 1. 期初借款本金 = 上一年期末借款累计
        begin_loan = end_loan_last
        # 2. 本期借款：用户输入的当年借款额
        current_loan = loan_plan_dict.get(year, 0.0)
        # 3. 本期计息 = (期初借款 + 本期借款/2) × 年利率
        current_interest = (begin_loan + current_loan / 2) * rate
        # 4. 本期付息 = 本期计息（利息当期全额偿还，不滚入本金）
        repay_interest = current_interest
        # 5. 本期还本：按计划还本，最多还清剩余本金，避免出现负数
        plan_repay = repay_principal_plan.get(year, 0.0)
        max_repayable = begin_loan + current_loan + current_interest - repay_interest
        # 一行搞定：非最后一年按计划还，最后一年直接结清全部剩余本金
        repay_principal = min(plan_repay, max_repayable) if year < last_loan_year else max_repayable
        # 6. 本期本息偿还合计
        total_repay = repay_principal + repay_interest
        # 7. 期末借款累计 = 期初 + 本期借款 + 本期计息 - 本期付息 - 本期还本
        end_loan = begin_loan + current_loan + current_interest - repay_interest - repay_principal
        end_loan = max(end_loan, 0.0)  # 余额不能为负

        # 填入表格，完全匹配你给的表结构
        loan_df.loc[year, "期初借款本金(万元)"] = round(begin_loan, 4)
        loan_df.loc[year, "本期借款(万元)"] = round(current_loan, 4)
        loan_df.loc[year, "本期计息(万元)"] = round(current_interest, 4)
        loan_df.loc[year, "本期还本(万元)"] = round(repay_principal, 4)
        loan_df.loc[year, "本期付息(万元)"] = round(repay_interest, 4)
        loan_df.loc[year, "本期本息偿还合计(万元)"] = round(total_repay, 4)
        loan_df.loc[year, "期末借款累计(万元)"] = round(end_loan, 4)

        # 更新迭代变量
        end_loan_last = end_loan

    # 提取每年的财务费用（当年付息额，用于总成本计算）
    financial_cost_dict = loan_df["本期付息(万元)"].to_dict()
    return loan_df, financial_cost_dict

# ===================== 税金及其附加测算函数（直接调用收入表数据，100%对齐无误差）=====================
def calc_taxes(all_years, month_dict, is_operate, income_df, resi_occupancy, operate_year_list, land_area, construction_cost):
    tax_df = pd.DataFrame(index=all_years)
    operate_year_index = {year: idx+1 for idx, year in enumerate(operate_year_list)}
    
    for year in all_years:
        if not is_operate[year]:
            tax_df.loc[year, "增值税(万元)"] = tax_df.loc[year, "印花税(万元)"] = tax_df.loc[year, "城镇维护建设税(万元)"] = tax_df.loc[year, "教育附加和地方教育附加税(万元)"] = tax_df.loc[year, "房产税(万元)"] = tax_df.loc[year, "城镇土地使用税(万元)"] = tax_df.loc[year, "税金及其附加总和(万元)"] = 0.0
        else:
            # 直接从收入表拿现成的、已经算好的收入数据，100%和收入表对齐
            resi_rent_year = income_df.loc[year, "住宅租金收入(万元)"]
            park_rent_year = income_df.loc[year, "车位收入(万元)"]
            total_income_year = income_df.loc[year, "总收入(万元)"]
            # 其他基础参数
            occ = resi_occupancy.get(year, 0)
            months = month_dict[year]
            
            # 严格按你给的公式计算，基数完全和收入表一致
            vat = (resi_rent_year * (0.015 / 1.05)) + (park_rent_year * (0.09 / 1.09))
            stamp = total_income_year * (0.0005 / 1.09)
            city_maintain = vat * 0.07
            edu_surcharge = vat * 0.05
            
            # 房产税：前3年免征，严格按公式计算
            if operate_year_index[year] <= 3:
                property_tax = 0.0
            else:
                resi_property = resi_rent_year * occ * (0.04 / 1.05)
                park_property = park_rent_year * (0.12 / 1.09)
                construction_property = (construction_cost * 0.7 * 0.012 / 1.09) * (1 - occ) * (months / 12)
                property_tax = resi_property + park_property + construction_property
            
            # 城镇土地使用税：3元/㎡，转万元
            land_use_tax = land_area * 3 / 10000
            # 税金总和
            total_tax = vat + stamp + city_maintain + edu_surcharge + property_tax + land_use_tax
            
            # 填入表格
            tax_df.loc[year, "增值税(万元)"] = round(vat, 4)
            tax_df.loc[year, "印花税(万元)"] = round(stamp, 4)
            tax_df.loc[year, "城镇维护建设税(万元)"] = round(city_maintain, 4)
            tax_df.loc[year, "教育附加和地方教育附加税(万元)"] = round(edu_surcharge, 4)
            tax_df.loc[year, "房产税(万元)"] = round(property_tax, 4)
            tax_df.loc[year, "城镇土地使用税(万元)"] = round(land_use_tax, 4)
            tax_df.loc[year, "税金及其附加总和(万元)"] = round(total_tax, 4)
    
    return tax_df

# ===================== 损益表测算函数（修复弥补亏损逻辑+新增净利润）=====================
def calc_profit(all_years, income_df, total_cost_df, tax_df, is_sale_project=False):
    profit_df = pd.DataFrame(index=all_years)
    
    # 1-3行：直接调用现成数据
    profit_df["总收入(万元)"] = income_df["总收入(万元)"]
    profit_df["总成本费用(万元)"] = total_cost_df["总成本费用(不含建设期财务费用、不含税金)(万元)"]
    profit_df["税金及其附加总和(万元)"] = tax_df["税金及其附加总和(万元)"]
    
    # 4. 利润总额（出售型不扣除税金及其附加，出租型保持原有逻辑）
    if is_sale_project:
        profit_df["利润总额(万元)"] = round(profit_df["总收入(万元)"] - profit_df["总成本费用(万元)"], 4)
    else:
        profit_df["利润总额(万元)"] = round(profit_df["总收入(万元)"] - profit_df["总成本费用(万元)"] - profit_df["税金及其附加总和(万元)"], 4)
    
    # 5-6. 修复弥补亏损、应纳税所得额核心逻辑
    loss_history = []
    first_profit_year = None
    弥补亏损_dict = {}
    应纳税所得额_dict = {}
    last_negative_taxable = 0
    loss_years_used = 0
    
    for idx, year in enumerate(all_years):
        current_profit = profit_df.loc[year, "利润总额(万元)"]
        loss_history.append(current_profit)
        
        # 寻找首次盈利年份
        if first_profit_year is None and current_profit > 0:
            first_profit_year = year
        
        # 【核心修复】弥补亏损逻辑，符号完全匹配公式
        if first_profit_year is None:
            # 首次盈利前，弥补亏损为0
            弥补亏损 = 0.0
        else:
            if loss_years_used >= 5:
                # 最多弥补5年，后续为0
                弥补亏损 = 0.0
            else:
                if year == first_profit_year:
                    # 首次盈利：弥补亏损=前5年利润总额之和（亏损为负数，直接求和）
                    prev_5_years = loss_history[max(0, idx-5):idx]
                    弥补亏损 = sum(prev_5_years)
                else:
                    # 后续年份：上一年应纳税所得额为负，直接结转
                    弥补亏损 = last_negative_taxable if last_negative_taxable < 0 else 0.0
        
        # 应纳税所得额=利润总额+弥补亏损（弥补亏损为负数，自动扣减亏损）
        应纳税所得额 = current_profit + 弥补亏损
        
        # 更新迭代变量
        if first_profit_year is not None and 弥补亏损 != 0:
            loss_years_used += 1
        last_negative_taxable = 应纳税所得额 if 应纳税所得额 < 0 else 0
        
        # 存入字典
        弥补亏损_dict[year] = round(弥补亏损, 4)
        应纳税所得额_dict[year] = round(应纳税所得额, 4)
    
    # 填入表格
    profit_df["弥补亏损(万元)"] = pd.Series(弥补亏损_dict)
    profit_df["应纳税所得额(万元)"] = pd.Series(应纳税所得额_dict)
    
    # 7. 所得税
    profit_df["所得税(万元)"] = profit_df["应纳税所得额(万元)"].apply(lambda x: round(x * 0.25, 4) if x > 0 else 0.0)
    
    # 8. 新增：净利润=利润总额-所得税
    profit_df["净利润(万元)"] = round(profit_df["利润总额(万元)"] - profit_df["所得税(万元)"], 4)
    
    return profit_df

# ===================== 结果展示区 =====================
# 仅AI模式允许使用历史快照；普通模式必须点击按钮才测算
if calc_button or has_result_snapshot_for_current_page(current_page_key):
    try:
        use_snapshot_only = (not calc_button) and has_result_snapshot_for_current_page(current_page_key)
        if use_snapshot_only:
            snap = get_ai_result_snapshot()

            total_income = snap["total_income"]
            total_cost = snap["total_cost"]
            total_interest = snap["total_interest"]
            total_net_profit = snap["total_net_profit"]
            interest_coverage_ratio = snap["interest_coverage_ratio"]
            total_npv_sum = snap["total_npv_sum"]
            irr_value = snap["irr_value"]

            income_df_T = snap["income_df_T"]
            cost_df_T = snap["cost_df_T"]
            loan_df_T = snap["loan_df_T"]
            profit_df_T = snap["profit_df_T"]
            cf_df_T = snap["cf_df_T"]
            tax_df_T = snap.get("tax_df_T", pd.DataFrame())
            rental_cost_df_T = snap.get("rental_cost_df_T", pd.DataFrame())

            project_name = snap.get("project_name", "测算项目")
            project_type = snap.get("project_type", project_type)

            # 关键：聊天上下文直接从快照恢复，不再依赖下面重新拼装
            if snap.get("ai_result_context"):
                st.session_state["ai_result_context"] = snap.get("ai_result_context", {})

            # AI模式说明所需内容也恢复
            if snap.get("ai_core_input") is not None:
                st.session_state["ai_core_input"] = snap.get("ai_core_input", {})
            if snap.get("ai_params") is not None:
                st.session_state["ai_params"] = snap.get("ai_params", {})
            if snap.get("ai_similar_projects") is not None:
                st.session_state["ai_similar_projects"] = snap.get("ai_similar_projects", [])
            if snap.get("ai_similar_project_names") is not None:
                st.session_state["ai_similar_project_names"] = snap.get("ai_similar_project_names", [])
        st.session_state["ai_calc_trigger"] = False
        # 前置校验，避免参数缺失报错
        show_resi = st.session_state.get("show_resi", True) #不设置这个就会报错
        if not operate_years: st.error("❌ 请先在「1. 项目基本信息」中设置运营期年份！"); st.stop()
        if  show_resi and not occupancy_ramp_dict: st.error("❌ 请先设置住宅爬坡期年份及对应出租率！"); st.stop() #加双重认证，防止跳过住宅就无法输出
        if stable_start > stable_end: st.error("❌ 住宅稳定期起始年不能晚于结束年！"); st.stop()
        if not loan_plan_dict: st.warning("⚠️ 未设置银行借款计划，财务费用将为0")
        
        # 1. 基础年份数据生成
        all_years, month_dict, is_operate = generate_year_list(build_years, operate_years)
        operate_start_year = operate_years[0]  # 运营期起始年，用于还款判断
        # ========== 【新增1行，仅此改动】定义operate_year_list，修复未定义报错 ==========
        operate_year_list = [y for y in all_years if is_operate[y]]
    
        show_park = st.session_state.get("show_park", True)
        if not show_park: #防止不选车位后报错
            park_count = 0
            park_rent_start_price = 0
            park_income_ratio = 0
            park_occupancy_ramp_dict = {}
            park_stable_start = 0
            park_stable_end = 0
            park_occupancy_stable = 0
        
        # 2. 收入测算（原有逻辑完全不变）
        income_df, resi_occupancy, resi_rent_price, park_occupancy, park_rent_price = calc_income(
            all_years, month_dict, is_operate,
            residential_area, rent_start_price,
            rent_increase_span, rent_increase_rate,
            occupancy_ramp_dict, stable_start, stable_end, occupancy_stable,
            park_count, park_rent_start_price, park_income_ratio,
            park_occupancy_ramp_dict, park_stable_start, park_stable_end, park_occupancy_stable,
            other_income_name, other_income_total
        )
        # ===================== 【仅改参数·100%复用】出售类新增收入项 ======================
        if "sale_and_commercial" in PROJECT_CONFIG[project_type].get("ui_components", []):
            # 1. 商业出租：完全复用calc_income函数，传入商业专属参数，零重复代码
            comm_income_df, _, _, _, _ = calc_income(
                all_years, month_dict, is_operate,
                comm_area, comm_rent_start_price,
                comm_rent_increase_span, comm_rent_increase_rate,
                comm_occupancy_ramp_dict, comm_stable_start, comm_stable_end, comm_occupancy_stable,
                0, 0, 0, {}, 0, 0, 0, "无", 0  # 车位、其他收入全传0，仅计算商业租金
             )
            income_df["商业出租收入(万元)"] = comm_income_df["住宅租金收入(万元)"]
            #不加下面的这部分 就会报错(出租净收益现值)
            rental_cost_df = calc_rental_operation_table(
                all_years=all_years,
                is_operate=is_operate,
                operate_year_list=operate_year_list,
                comm_area=comm_area,
                comm_rent_start_price=comm_rent_start_price,
                comm_rent_increase_span=comm_rent_increase_span,
                comm_rent_increase_rate=comm_rent_increase_rate,
                comm_occupancy_ramp_dict=comm_occupancy_ramp_dict,
                comm_stable_start=comm_stable_start,
                comm_stable_end=comm_stable_end,
                comm_occupancy_stable=comm_occupancy_stable,
                park_count=park_count,
                land_cost=land_cost,
                construction_cost=construction_cost,
                infra_cost=infra_cost,
                other_eng_cost=other_eng_cost,
                lease_months=lease_months if 'lease_months' in locals() else 12,
                land_use_area=land_use_area,
                project_input_tax=project_input_tax,
                comm_custom_increase_list=comm_custom_increase_list,
            )
            # 【核心】顺便把现值赋给 income_df()
            income_df["出租净收益现值(万元)"] = rental_cost_df["出租净收益现值(万元)"].fillna(0)
            #2.配保房销售逻辑
            for year in all_years:
                sale_rate = sale_ramp_dict.get(year, 0.0)  # 只有你选的销售年份有销售率，其他年份0
                income_df.loc[year, "配保房销售收入(万元)"] = round(sale_area * sale_avg_price * sale_rate / 10000, 4) if is_operate[year] else 0
            
            # 3. 更新总收入：原有逻辑完全不动
            #income_df["总收入(万元)"] = income_df["配保房销售收入(万元)"] + income_df[f"{other_income_name}(万元)"]+ income_df["住宅租金收入(万元)"] + income_df["车位收入(万元)"] +income_df["出租净收益现值(万元)"] +income_df["总收入(万元)"] 
        
        # 3. 经营成本测算
        park_income_dict = income_df["车位收入(万元)"].to_dict()
        operating_cost_df = calc_operating_cost(
            all_years, month_dict, is_operate,
            residential_area, resi_occupancy, resi_rent_price,
            park_income_dict, total_build_area, manage_coeff,
            residential_decoration_cost, house_type, total_investment, operate_years
        )
        
        # 4. 还本付息与财务费用测算（完全基于配置）
        current_config = PROJECT_CONFIG[project_type]
        loan_df, financial_cost_dict = calc_loan_repayment(
            all_years, operate_start_year,
            loan_plan_dict, loan_annual_rate,
            first_repay_ratio, repay_increase_rate, loan_total_years,
            custom_repay_plan=repay_plan_dict,
            project_config=current_config
        )
        
        # 4.5 新增：税金及其附加测算
        tax_df = calc_taxes(
            all_years, month_dict, is_operate,
            income_df, resi_occupancy, operate_years,
            land_area, construction_cost
        )
        
        # 5. 生成总成本费用表（经营成本+财务费用，不含税金）
        total_cost_df = operating_cost_df.copy()
        build_year_set, operate_year_set = set(build_years), set(operate_years)
        total_cost_df["财务费用(建设期)(万元)"] = total_cost_df.index.map(lambda y: round(financial_cost_dict.get(y, 0.0), 4) if y in build_year_set else 0.0)
        total_cost_df["财务费用(运营期)(万元)"] = total_cost_df.index.map(lambda y: round(financial_cost_dict.get(y, 0.0), 4) if y in operate_year_set else 0.0)
        total_cost_df["税金及其附加总和(万元)"] = tax_df["税金及其附加总和(万元)"]
        # 总成本费用：仅含经营成本+运营期财务费用，不含税金、不含建设期财务费用
        total_cost_df["总成本费用(不含建设期财务费用、不含税金)(万元)"] = round(total_cost_df["经营成本(万元)"] + total_cost_df["财务费用(运营期)(万元)"], 4)
    
        # ===================== 【最小新增】出售类专属总成本费用表重写 =====================
        if project_type == "出售类(配保房/可售型人才房等)":
            # 初始化出售类总成本表，index和原有表完全一致
            sale_cost_df = pd.DataFrame(index=all_years)
            # 基础参数预计算（一行搞定，防除0）
            area_total = sale_area + comm_area
            area_ratio_sale = sale_area / area_total if area_total != 0 else 0.0
            area_ratio_comm = 1 - area_ratio_sale
            land_deduct_total = sale_area * land_floor_price / 10000  # 地价抵减总额（转万元）
            non_sale_dev_cost = land_cost + dev_cost  # 非配售开发成本=土地成本费+开发成本费
            build_fin_total = total_cost_df["财务费用(建设期)(万元)"].sum()  # 建设期财务费用总额
            total_sale_income_all = income_df["配保房销售收入(万元)"].sum()
             # 销售部分全周期合计(总投资-建设期财务费用×销售面积比-配保房收入×1.5%)
            # 【新增1行】全周期销售费用合计（固定值）
            total_sale_fee_all = total_sale_income_all * 0.015
            total_dev_cost_sale_base = total_investment - build_fin_total * area_ratio_sale-total_sale_income_all * 0.015
             # 折旧摊销部分全周期合计
            total_dev_cost_dep_base = (non_sale_dev_cost - build_fin_total * area_ratio_comm) * 0.8
            
            
            # 预计算累计值变量
            cum_output_vat = 0.0
            cum_input_vat = 0.0
            cum_vat_total = 0.0
            cum_vat_surcharge_total = 0.0
            
            # 按年份循环计算所有指标（一行公式，严格匹配你的要求）
            for year in all_years:
                # 1. 基础当年值
                sale_income_year = income_df.loc[year, "配保房销售收入(万元)"]
                sale_rate_year = sale_ramp_dict.get(year, 0.0)
                # 【新增1行】取当年其他收入
                other_income_year = income_df.loc[year, f"{other_income_name}(万元)"]
                # 2. 销售费用=当年配保房销售收入×1.5%
                sale_fee_year = sale_income_year * 0.015
                # 3. 增值税销项税=(当年销售款-地价抵减总额×当年销售率)×9%/(1+9%)
                output_vat_year = (sale_income_year + other_income_year - land_deduct_total * sale_rate_year) * (0.09 / 1.09) if sale_income_year > 0 else 0.0
                # 4. 增值税进项税（修正公式笔误，一行搞定）
                input_vat_6 = (other_eng_cost /area_ratio_comm + total_sale_fee_all) * sale_rate_year * (0.06 / 1.06)
                input_vat_9 = (sale_construction_cost + sale_infra_cost+construction_cost + infra_cost) * sale_rate_year * (0.09 / 1.09)
                input_vat_year = input_vat_6 + input_vat_9
                # 5. 累计值计算
                cum_output_vat += output_vat_year
                cum_input_vat += input_vat_year
                vat_year = max(cum_output_vat - cum_input_vat - cum_vat_total, 0.0)
                cum_vat_total += vat_year
                vat_surcharge_year = vat_year * 0.12
                cum_vat_surcharge_total += vat_surcharge_year
                # 6. 印花税=当期销售款×印花税率/(1+9%)
                stamp_year = sale_income_year * stamp_tax_rate / 1.09 if sale_income_year > 0 else 0.0
                # 7. 销售税金及其附加=增值税+增值税附加+印花税
                sale_tax_total_year = vat_year + vat_surcharge_year + stamp_year
                # 8. 当年开发成本（销售部分）= 全周期合计基数 × 当年销售率
                dev_cost_sale_year = total_dev_cost_sale_base * sale_rate_year
                # 9. 当年开发成本（折旧摊销部分）= 全周期合计基数 × 当年销售率
                dev_cost_dep_year = total_dev_cost_dep_base * sale_rate_year
    
                # 当年地价款抵减额（匹配销售率）
                land_deduct_year = land_deduct_total * sale_rate_year
                # 填入表格（和原有财务费用、总成本列完全对齐）
                sale_cost_df.loc[year, "累计开发成本（销售部分）(万元)"] = round(dev_cost_sale_year, 4)
                sale_cost_df.loc[year, "累计开发成本（折旧摊销部分）(万元)"] = round(dev_cost_dep_year, 4)
                sale_cost_df.loc[year, "销售费用(万元)"] = round(sale_fee_year, 4)
                sale_cost_df.loc[year, "销售税金及其附加(万元)"] = round(sale_tax_total_year, 4)
                # 新增税金核对行（复用循环内已计算的变量，无额外计算）
                sale_cost_df.loc[year, "增值税(万元)"] = round(vat_year, 4)
                sale_cost_df.loc[year, "增值税销项税额(万元)"] = round(output_vat_year, 4)
                sale_cost_df.loc[year, "增值税进项税额(万元)"] = round(input_vat_year, 4)
                sale_cost_df.loc[year, "地价款抵减(万元)"] = round(land_deduct_year, 4)
                sale_cost_df.loc[year, "增值税附加(万元)"] = round(vat_surcharge_year, 4)
                sale_cost_df.loc[year, "财务费用(建设期)(万元)"] = total_cost_df.loc[year, "财务费用(建设期)(万元)"]
                sale_cost_df.loc[year, "财务费用(运营期)(万元)"] = total_cost_df.loc[year, "财务费用(运营期)(万元)"]
                # 总成本费用=开发成本销售部分+开发成本折旧摊部分+销售费用+销售税金+运营期财务费用
                total_cost_year = dev_cost_sale_year + dev_cost_dep_year + sale_fee_year + sale_tax_total_year + total_cost_df.loc[year, "财务费用(建设期)(万元)"]+total_cost_df.loc[year, "财务费用(运营期)(万元)"]
                sale_cost_df.loc[year, "总成本费用(不含建设期财务费用、不含税金)(万元)"] = round(total_cost_year, 4)
            
            # 替换原有总成本表，仅出售类生效
            total_cost_df = sale_cost_df
        # ===================== 出售类总成本表重写结束 =====================
        # 【关键：统一计算最终正确的总收入，确保损益表和收入明细表用的是同一套数据】
        if project_type == "出售类(配保房/可售型人才房等)":
            # 先把出租净收益现值同步到收入表
            income_df["出租净收益现值(万元)"] = rental_cost_df["出租净收益现值(万元)"].fillna(0)
            # 重新计算最终总收入，和收入明细表的公式完全一致，无重复累加
            income_df["总收入(万元)"] = (income_df["配保房销售收入(万元)"]  + income_df["出租净收益现值(万元)"] + income_df["住宅租金收入(万元)"] + income_df["车位收入(万元)"] + income_df[f"{other_income_name}(万元)"] )
        # 提前计算损益表，用于核心指标的净利润
        is_sale = (project_type == "出售类(配保房/可售型人才房等)")
        profit_df = calc_profit(all_years, income_df, total_cost_df, tax_df, is_sale_project=is_sale)
    
        # ===================== 新增：全投资现金流量表计算 =====================
        cf_df = pd.DataFrame(index=all_years)
        # 1. 现金流入：直接调用现成的总收入
        cf_df["现金流入(万元)"] = income_df["总收入(万元)"]
    
        # 现金流入：先按项目类型拆分明细，再汇总
        if project_type == "出售类(配保房/可售型人才房等)":
            # 1. 先定义各项明细
            cf_df["配保房销售收入(万元)"] = income_df["配保房销售收入(万元)"] if "配保房销售收入(万元)" in income_df.columns else 0
            cf_df["其他收入(万元)"] = income_df[f"{other_income_name}(万元)"] if f"{other_income_name}(万元)" in income_df.columns else 0
            cf_df["商业出租收入(万元)"] = income_df["商业出租收入(万元)"] if "商业出租收入(万元)" in income_df.columns else 0
            #cf_df["商业出租收入(万元)"] = rental_cost_df.get("商业出租收入(万元)", 0.0).astype(float)
            # 回收固定资产余值（公式不变，先设为0，再给最后一行赋值）
            area_total = sale_area + comm_area
            comm_ratio = comm_area / area_total if area_total != 0 else 0
            recover_fixed = (land_cost + dev_cost - total_cost_df["财务费用(建设期)(万元)"].sum() * comm_ratio) * 0.2
            cf_df["回收固定资产余值(万元)"] = 0.0
            operate_first_year = operate_years[0]  # 👈 改这里：[-1]→[0]，取运营期第一年
            if operate_first_year in cf_df.index:
                cf_df.loc[operate_first_year, "回收固定资产余值(万元)"] = recover_fixed  # 👈 改这里：变量名对应
        
            # 2. 关键：现金流入 = 四项之和（解决合计为/的问题）
            cf_df["现金流入(万元)"] = (cf_df["配保房销售收入(万元)"] + cf_df["其他收入(万元)"] + cf_df["商业出租收入(万元)"] + cf_df["回收固定资产余值(万元)"])
    
            # 🔥 【仅新增这一段：出售类专属现金流出，其他全不动】
            area_total = sale_area + comm_area
            dev_cost_base = total_investment * (sale_area / area_total) if area_total != 0 else 0.0
            # 初始化新列
            cf_df[["开发成本投资(万元)", "销售费用(万元)", "销售税金及附加(万元)", "出租经营税金(万元)", "出租营运成本(万元)", "调整所得税(万元)"]] = 0.0
            # 【新增1行：填入用户输入的开发成本投资，其余年份保持默认0】
            for y in dev_cost_plan_dict: cf_df.loc[y, "开发成本投资(万元)"] = round(dev_cost_plan_dict[y],4)
            
            # 合计计算：严格按你给的公式
            for year in all_years:
                # 一行提取所有现成数据
                sale_fee, sale_tax = total_cost_df.loc[year, ["销售费用(万元)", "销售税金及其附加(万元)"]]
                rent_tax = rental_cost_df.loc[year, "出租经营税金合计(万元)"] if year in rental_cost_df.index else 0.0
                rent_cost = rental_cost_df.loc[year, "出租营运成本合计(万元)"] if year in rental_cost_df.index else 0.0
                build_fin_fee = total_cost_df.loc[year, "财务费用(建设期)(万元)"]
                dev_cost_sale, dev_cost_dep = total_cost_df.loc[year, ["累计开发成本（销售部分）(万元)", "累计开发成本（折旧摊销部分）(万元)"]]
    
                dev_cost_total = dev_cost_base - total_cost_df["财务费用(建设期)(万元)"].sum() - total_cost_df["销售费用(万元)"].sum()
                
                # 一行计算调整所得税（负数自动取0）
                adjust_tax = max( (cf_df.loc[year, "现金流入(万元)"] - cf_df.loc[year, "回收固定资产余值(万元)"] - (dev_cost_sale + dev_cost_dep + sale_fee + sale_tax + rent_cost + rent_tax)) * 0.25, 0.0 )
            
                # 一行填入所有数值
                 # 🔥 修复2：年度开发成本投资 = 0（不参与年度计算，仅合计有数）
                cf_df.loc[year, ["销售费用(万元)", "销售税金及附加(万元)", "出租经营税金(万元)", "出租营运成本(万元)", "调整所得税(万元)"]] = [round(sale_fee,4), round(sale_tax,4), round(rent_tax,4), round(rent_cost,4), round(adjust_tax,4)]
                # 🔥 修复3：年度现金流出合计 = 仅费用+税，不加开发成本
               # 修复后：现金流出合计 = 当年开发成本投资 + 销售费用 + 销售税金 + 出租税金 + 出租成本 + 调整所得税
                cf_df.loc[year, "现金流出合计(万元)"] = round( cf_df.loc[year, "开发成本投资(万元)"] + sale_fee + sale_tax + rent_tax + rent_cost + adjust_tax, 4)
                cf_df = cf_df.reindex(columns=["现金流入(万元)","配保房销售收入(万元)", "其他收入(万元)", "商业出租收入(万元)", "回收固定资产余值(万元)", "现金流出合计(万元)", "开发成本投资(万元)", "销售费用(万元)", "销售税金及附加(万元)", "出租经营税金(万元)", "出租营运成本(万元)", "调整所得税(万元)"])
        else:
            # 其他类型保持原来的逻辑不变
            cf_df["现金流入(万元)"] = income_df["总收入(万元)"]
    
        # 2. 现金流出：全调用现成表数据，按你的公式汇总
        # 2. 现金流出：全调用现成表数据，按你的公式汇总
        if project_type != "出售类(配保房/可售型人才房等)": 
            for year in all_years:
                build_invest = invest_plan_dict.get(year, 0.0)
                tax_total = tax_df.loc[year, "税金及其附加总和(万元)"]
                # 【最小修复】用get方法兜底，出售类无对应列自动返回0，不触发KeyError
                manage_total = total_cost_df.loc[year, :].get("管理费用(住房)(万元)", 0) + total_cost_df.loc[year, :].get("管理费用(停车位)(万元)", 0)
                vacancy_fee = total_cost_df.loc[year, :].get("空置期物业管理费(万元)", 0)
                repair_fee = total_cost_df.loc[year, :].get("维修费用(万元)", 0)
                insurance_fee = total_cost_df.loc[year, :].get("保险费(万元)", 0)
                decoration_reset = total_cost_df.loc[year, :].get("装修重置费(万元)", 0)
                maintain_fund = total_cost_df.loc[year, :].get("日常物业维修基金(万元)", 0)
                income_tax = profit_df.loc[year, "所得税(万元)"]
            
                # 现金流出合计
                cash_out_total = build_invest + tax_total + manage_total + vacancy_fee + repair_fee + insurance_fee + decoration_reset + maintain_fund + income_tax
                cf_df.loc[year, "建设投资(万元)"] = round(build_invest, 4)
                cf_df.loc[year, "现金流出合计(万元)"] = round(cash_out_total, 4)
    
        # 3. 净现金流量
        cf_df["净现金流量(万元)"] = round(cf_df["现金流入(万元)"] - cf_df["现金流出合计(万元)"], 4)
    
        # 4. 累计净现金流量
        cum_cf_list = []
        last_cum_cf = 0
        for year in all_years:
            current_cum = cf_df.loc[year, "净现金流量(万元)"] + last_cum_cf
            cum_cf_list.append(current_cum)
            last_cum_cf = current_cum
        cf_df["累计净现金流量(万元)"] = round(pd.Series(cum_cf_list, index=all_years), 4)
    
        # 5. 净现值（严格按你给的公式计算）
        discount_rate_decimal = discount_rate / 100
        npv_list = []
        for idx, year in enumerate(all_years):
            n = idx + 1  # 从建设期开始的第n年，从1开始计数
            discount_factor = (1 + discount_rate_decimal) ** (n - 0.5)
            current_npv = cf_df.loc[year, "净现金流量(万元)"] / discount_factor
            npv_list.append(current_npv)
        cf_df["净现值(万元)"] = round(pd.Series(npv_list, index=all_years), 4)
    
        # 6. 累计净现值
        cum_npv_list = []
        last_cum_npv = 0
        for year in all_years:
            current_cum_npv = cf_df.loc[year, "净现值(万元)"] + last_cum_npv
            cum_npv_list.append(current_cum_npv)
            last_cum_npv = current_cum_npv
        cf_df["累计净现值(万元)"] = round(pd.Series(cum_npv_list, index=all_years), 4)
      
        # 6. 统一给所有表格加「全周期合计列」（放在第二列，和之前格式完全一致）
        # --- 收入表处理 ---
        income_df_T = income_df.T
       # 【最小改动：仅加if判断，分项目类型处理】
        if project_type == "出售类(配保房/可售型人才房等)":
         # 仅出售类：配保房+商业+住宅的顺序，且都算合计
            # 仅出售类：配保房+商业+住宅的顺序，且都算合计
            income_sum_rows = ["配保房销售收入(万元)", "住宅租金收入(万元)", "出租净收益现值(万元)", "车位收入(万元)", f"{other_income_name}(万元)","总收入(万元)"]
            income_df_T["全周期合计(万元)"] = income_df_T.apply(
            lambda row: round(row.sum(), 4) if row.name in income_sum_rows else "/", axis=1
            )
            # 仅出售类：调整行顺序
            income_df_T = income_df_T.reindex(income_sum_rows + [idx for idx in income_df_T.index if idx not in income_sum_rows])
        else:
        # 出租型：完全保持你原来的逻辑，一丝不动
            income_sum_rows = ["住宅租金收入(万元)", "车位收入(万元)", f"{other_income_name}(万元)", "总收入(万元)"]
            income_df_T["全周期合计(万元)"] = income_df_T.apply(
                lambda row: round(row.sum(), 4) if row.name in income_sum_rows else "/", axis=1
        )
        income_df_T = income_df_T[ ["全周期合计(万元)"] + [col for col in income_df_T.columns if col != "全周期合计(万元)"] ]
        income_df_T = income_df_T.fillna("/")
    
         # --- 总成本费用表处理 ---
        cost_df_T = total_cost_df.T
        if project_type == "出售类(配保房/可售型人才房等)":
            # 出售类：仅对数值行求和，严格匹配新的行
            cost_sum_rows = ["累计开发成本（销售部分）(万元)", "累计开发成本（折旧摊销部分）(万元)", "销售费用(万元)", "销售税金及其附加(万元)", "增值税(万元)","增值税销项税额(万元)","增值税进项税额(万元)","地价款抵减(万元)","增值税附加(万元)","财务费用(建设期)(万元)", "财务费用(运营期)(万元)", "总成本费用(不含建设期财务费用、不含税金)(万元)"]
        else:
            # 出租型：完全保留原有逻辑，一丝不动
            cost_sum_rows = ["管理费用(住房)(万元)", "管理费用(停车位)(万元)", "保险费(万元)", "维修费用(万元)", "日常物业维修基金(万元)", "空置期物业管理费(万元)", "装修重置费(万元)", "折旧摊销(万元)", "经营成本(万元)", "财务费用(建设期)(万元)", "财务费用(运营期)(万元)", "税金及其附加总和(万元)", "总成本费用(不含建设期财务费用、不含税金)(万元)"]
        #cost_sum_rows = ["管理费用(住房)(万元)", "管理费用(停车位)(万元)", "保险费(万元)", "维修费用(万元)", "日常物业维修基金(万元)", "空置期物业管理费(万元)", "装修重置费(万元)", "折旧摊销(万元)", "经营成本(万元)", "财务费用(建设期)(万元)", "财务费用(运营期)(万元)", "税金及其附加总和(万元)", "总成本费用(不含建设期财务费用、不含税金)(万元)"]
        cost_df_T["全周期合计(万元)"] = cost_df_T.apply(lambda row: round(row.sum(), 4) if row.name in cost_sum_rows else "/", axis=1)
        cost_df_T = cost_df_T[ ["全周期合计(万元)"] + [col for col in cost_df_T.columns if col != "全周期合计(万元)"] ]
    
        # --- 还本付息表处理 ---
        loan_df_T = loan_df.T
        loan_df_T["全周期合计(万元)"] = loan_df_T.sum(axis=1).round(4)
        # 期初/期末借款的合计无意义，填/
        loan_no_sum_rows = ["期初借款本金(万元)", "期末借款累计(万元)"]
        loan_df_T.loc[:, "全周期合计(万元)"] = loan_df_T.apply(
            lambda row: np.nan if row.name in loan_no_sum_rows else row["全周期合计(万元)"], axis=1
        )
        loan_df_T = loan_df_T[ ["全周期合计(万元)"] + [col for col in loan_df_T.columns if col != "全周期合计(万元)"] ]
    
        # 7. 计算最终核心指标
        if project_type == "出售类(配保房/可售型人才房等)":
            total_income = round(income_df["配保房销售收入(万元)"].sum()+ income_df["出租净收益现值(万元)"].sum()+ income_df["住宅租金收入(万元)"].sum()+ income_df["车位收入(万元)"].sum()+ income_df[f"{other_income_name}(万元)"].sum(),2)
        else:
            total_income = round(income_df["总收入(万元)"].sum(), 2)
        #total_income = round(income_df["总收入(万元)"].sum(), 2)
        total_cost = round(total_cost_df["总成本费用(不含建设期财务费用、不含税金)(万元)"].sum(), 2)
        total_interest = round(loan_df["本期付息(万元)"].sum(), 2)
        total_net_profit = round(profit_df["净利润(万元)"].sum(), 2)
        
         # 新增：利息保障倍数计算（简化版：借款期从建设期第一年开始）
        # 1. 简化判断：借款期起始年=建设期第一年，结束年=起始年+借款年限-1
        first_loan_year = min(build_years) if build_years else min(all_years)
        last_loan_year = first_loan_year + loan_total_years -1
        loan_period_valid_years = [y for y in all_years if first_loan_year <= y <= last_loan_year]
        
        # 2. 提取核心数据
        build_fin_cost = total_cost_df["财务费用(建设期)(万元)"].sum()
        operate_fin_cost = total_cost_df["财务费用(运营期)(万元)"].sum()
        total_fin_cost = build_fin_cost + operate_fin_cost
        loan_period_profit = profit_df.loc[loan_period_valid_years, "利润总额(万元)"].sum()
        
        # 3. 计算倍数
        interest_coverage_ratio = round((loan_period_profit + operate_fin_cost) / total_fin_cost, 2) if total_fin_cost != 0 else 0.0
    
        # 全投资全周期累计净现值（取最后一年的累计值，即全周期最终净现值）
        total_npv_sum = round(cf_df["净现值(万元)"].sum(), 2)
    
            # ===================== 最终版IRR计算（已用你的2025-2095数据验证，结果准确）=====================
        # 1. 全局NPV计算函数（和Excel公式完全一致，供IRR调用）
        def calc_npv(rate, cash_flows):
            npv_total = 0.0
            for period, cf in enumerate(cash_flows):
                npv_total += cf / ((1 + rate) ** period)
            return npv_total
    
        # 2. 最终版Excel IRR函数（100%对齐Excel逻辑，针对你的亏损项目优化）
        def excel_irr_final(cash_flows, max_iter=1000, tol=1e-7):
            # 基础校验：必须有正有负的现金流
            has_positive = any(cf > 0 for cf in cash_flows)
            has_negative = any(cf < 0 for cf in cash_flows)
            if not has_positive or not has_negative:
                return None
    
            # 核心策略：你的项目是亏损项目（全周期现金流总和负），优先尝试-1%~-5%的负初始值（Excel优先解区间）
            priority_guesses = [-0.01, -0.02, -0.03, -0.04, -0.05, 0.0, 0.1]
    
            # 按优先级迭代计算，确保得到财务合理的解（避免极端值）
            for guess in priority_guesses:
                rate = guess
                for _ in range(max_iter):
                    current_npv = calc_npv(rate, cash_flows)
                    
                    # 收敛判断：NPV接近0，且IRR在财务合理区间（-50%~50%）
                    if abs(current_npv) < tol and -0.5 <= rate <= 0.5:
                        return rate
                    
                    # 计算导数（牛顿迭代必需），避免除以0
                    h = 1e-8
                    npv_h = calc_npv(rate + h, cash_flows)
                    derivative = (npv_h - current_npv) / h
                    if abs(derivative) < 1e-12:
                        break
                    
                    # 更新折现率，限制在合理区间（避免1000%这类极端值）
                    new_rate = rate - current_npv / derivative
                    new_rate = max(-0.5, min(new_rate, 0.5))
                    
                    # 迭代收敛，返回结果
                    if abs(new_rate - rate) < tol:
                        if -0.5 <= new_rate <= 0.5:
                            return new_rate
                        break
                    
                    rate = new_rate
    
            return None
    
        # 3. 提取你的净现金流量数据（和Excel时间顺序完全一致：2025-2095年）
        valid_years = sorted(list(set(build_years + operate_years)))
        cf_list = cf_df.loc[valid_years, "净现金流量(万元)"].tolist()
    
        # 4. 计算IRR并处理结果
        irr_result = excel_irr_final(cf_list)
        irr_value = f"{round(irr_result * 100, 2)} %" if irr_result is not None else "无法计算"
    
        # ===================== 【最小新增】项目类型特殊计算与指标展示（插在测算完成后、结果展示前）=====================
        current_config = PROJECT_CONFIG[project_type]
        extra_metrics = {}
        # 1. 招拍挂项目：调整建设投资（自动把土地成本加到建设期第一年的建设投资里）
        if "build_invest_adjust" in current_config["calc_rules"]:
            invest_plan_dict = current_config["calc_rules"]["build_invest_adjust"](invest_plan_dict, build_years, extra_params_global)
            # 重新计算现金流量表的建设投资（因为调整了投资计划）
            for year in all_years:
                cf_df.loc[year, "建设投资(万元)"] = round(invest_plan_dict.get(year, 0.0), 4)
                # 重新计算现金流出合计
                build_invest = invest_plan_dict.get(year, 0.0)
                tax_total = tax_df.loc[year, "税金及其附加总和(万元)"]
                manage_total = total_cost_df.loc[year, "管理费用(住房)(万元)"] + total_cost_df.loc[year, "管理费用(停车位)(万元)"]
                vacancy_fee = total_cost_df.loc[year, "空置期物业管理费(万元)"]
                repair_fee = total_cost_df.loc[year, "维修费用(万元)"]
                insurance_fee = total_cost_df.loc[year, "保险费(万元)"]
                decoration_reset = total_cost_df.loc[year, "装修重置费(万元)"]
                maintain_fund = total_cost_df.loc[year, "日常物业维修基金(万元)"]
                income_tax = profit_df.loc[year, "所得税(万元)"]
                cash_out_total = build_invest + tax_total + manage_total + vacancy_fee + repair_fee + insurance_fee + decoration_reset + maintain_fund + income_tax
                cf_df.loc[year, "现金流出合计(万元)"] = round(cash_out_total, 4)
            # 重新计算净现金流量、累计值、IRR相关
            cf_df["净现金流量(万元)"] = round(cf_df["现金流入(万元)"] - cf_df["现金流出合计(万元)"], 4)
            # 重新算累计净现金流量
            cum_cf_list = []
            last_cum_cf = 0
            for year in all_years:
                current_cum = cf_df.loc[year, "净现金流量(万元)"] + last_cum_cf
                cum_cf_list.append(current_cum)
                last_cum_cf = current_cum
            cf_df["累计净现金流量(万元)"] = round(pd.Series(cum_cf_list, index=all_years), 4)
            # 重新算净现值、累计净现值
            discount_rate_decimal = discount_rate / 100
            npv_list = []
            for idx, year in enumerate(all_years):
                n = idx + 1
                discount_factor = (1 + discount_rate_decimal) ** (n - 0.5)
                current_npv = cf_df.loc[year, "净现金流量(万元)"] / discount_factor
                npv_list.append(current_npv)
            cf_df["净现值(万元)"] = round(pd.Series(npv_list, index=all_years), 4)
            cum_npv_list = []
            last_cum_npv = 0
            for year in all_years:
                current_cum_npv = cf_df.loc[year, "净现值(万元)"] + last_cum_npv
                cum_npv_list.append(current_cum_npv)
                last_cum_npv = current_cum_npv
            cf_df["累计净现值(万元)"] = round(pd.Series(cum_npv_list, index=all_years), 4)
            # 重新计算IRR
            valid_years = sorted(list(set(build_years + operate_years)))
            cf_list = cf_df.loc[valid_years, "净现金流量(万元)"].tolist()
            irr_result = excel_irr_final(cf_list)
            irr_value = f"{round(irr_result * 100, 2)} %" if irr_result is not None else "无法计算"
            # 重新计算核心汇总指标
            total_npv_sum = round(cf_df["净现值(万元)"].sum(), 2)
        
        # 2. 计算额外指标
        total_invest = sum(invest_plan_dict.values())
        if "extra_metrics" in current_config["calc_rules"]:
            extra_metrics.update(current_config["calc_rules"]["extra_metrics"](extra_params_global, total_invest))
        if "invest_split" in current_config["calc_rules"]:
            extra_metrics.update(current_config["calc_rules"]["invest_split"](total_investment, extra_params_global))
        if "profit_split" in current_config["calc_rules"]:
            extra_metrics.update(current_config["calc_rules"]["profit_split"](total_net_profit, extra_params_global))
        
        # 3. 展示项目类型专属指标
        if current_config["show_metrics"] and extra_metrics:
            st.subheader(f"📌 {project_type}专属核心指标")
            cols = st.columns(len(current_config["show_metrics"]))
            for idx, metric_name in enumerate(current_config["show_metrics"]):
                cols[idx].metric(metric_name, extra_metrics.get(metric_name, "-"))
            st.markdown("---")
        # ===================== 【最小新增】项目类型特殊计算与指标展示（插在测算完成后、结果展示前）=====================


        # ===================== AI模式专属：测算说明 + 补参说明 =====================
                # ===================== AI模式专属：测算说明 + 补参说明 =====================
                # ===================== AI模式专属：测算说明 + 补参说明 =====================
        if is_ai_mode and st.session_state.get("ai_mode_ready", False):
            ai_core_input = st.session_state.get("ai_core_input", {})
            ai_params_state = st.session_state.get("ai_params", {})
            ai_similar_projects = st.session_state.get("ai_similar_projects", [])
            ai_similar_project_names = st.session_state.get("ai_similar_project_names", [])

            ai_summary_text = build_ai_summary_text(
                core_input=ai_core_input,
                project_type=project_type,
                total_income=total_income,
                total_cost=total_cost,
                total_net_profit=total_net_profit,
                irr_value=irr_value,
                total_npv_sum=total_npv_sum,
                similar_projects=ai_similar_projects
            )

            st.subheader("🧠 AI测算说明")
            st.info(ai_summary_text)

            with st.expander("📌 查看AI补齐参数明细", expanded=False):
                assumption_df = build_ai_assumption_table(
                    core_input=ai_core_input,
                    ai_params=ai_params_state,
                    similar_projects=ai_similar_projects
                )
                st.dataframe(assumption_df, use_container_width=True)

        # ===================== 所有模式统一生成AI问答上下文 =====================
        # ===================== 所有模式统一生成AI问答上下文 =====================
        if not use_snapshot_only:
            history_df_for_chat = load_builtin_history_projects()

            st.session_state["ai_result_context"] = build_general_project_chat_context(
                project_type=project_type,
                total_build_area=total_build_area,
                total_investment=total_investment,
                sale_avg_price=sale_avg_price,
                rent_start_price=rent_start_price,
                total_income=total_income,
                total_cost=total_cost,
                total_net_profit=total_net_profit,
                total_npv_sum=total_npv_sum,
                irr_value=irr_value,
                interest_coverage_ratio=interest_coverage_ratio,
                income_df=income_df,
                total_cost_df=total_cost_df,
                loan_df=loan_df,
                profit_df=profit_df,
                cf_df=cf_df,
                history_df=history_df_for_chat,
                tax_df=tax_df if 'tax_df' in locals() else None,
                rental_cost_df=rental_cost_df if 'rental_cost_df' in locals() else None,
                residential_area=residential_area if 'residential_area' in locals() else 0,
                comm_area=comm_area if 'comm_area' in locals() else 0,
                sale_area=sale_area if 'sale_area' in locals() else 0,
                comm_rent_start_price=comm_rent_start_price if 'comm_rent_start_price' in locals() else 0
            )

        # 只有用户刚完成新的测算时，才重置聊天记录
        if calc_button:
            st.session_state["ai_chat_messages"] = [
                {"role": "assistant", "content": "你好，我可以基于当前测算结果继续解释项目收益、成本、IRR、净现值、参考项目、异常指标和优化建议。"}
            ]
                # ===================== 保存结果快照，供聊天和刷新后继续展示 =====================
        
        # 8. 页面结果展示
        st.header("📊 测算结果")
        st.markdown("---")
        
        # --- 核心指标汇总 ---
        st.subheader("🎯 最终财务结果汇总")
        # 第一行：总收入、总成本
        col1, col2 = st.columns(2)
        with col1: st.metric("项目全周期总收入", f"{total_income} 万元")
        with col2: st.metric(":red[项目全周期总成本费用]", f"{total_cost} 万元")
        
        # 第二行：总付息、净利润
        col3, col4 = st.columns(2)
        with col3: st.metric("项目全周期总付息", f"{total_interest} 万元")
        with col4: st.metric("项目全周期净利润", f"{total_net_profit} 万元")
        
        # 第三行：利息保障倍数、净现值合计
        col5, col6 = st.columns(2)
        with col5: st.metric("利息保障倍数", f"{interest_coverage_ratio}")
        with col6: st.metric("净现值(合计)", f"{total_npv_sum} 万元")
        
        # 第四行：全投资内部收益率
        col7, _ = st.columns(2)
        with col7: st.metric("全投资内部收益率(IRR)", irr_value)
        
        st.markdown("---")
    
        # ===================== ✅ 出售类：插入出租营运成本表 =====================
        # 仅出售类项目显示该表，非出售类完全不执行，避免报错
        rental_cost_df = pd.DataFrame()
        if project_type == "出售类(配保房/可售型人才房等)":
            if use_snapshot_only and 'rental_cost_df_T' in locals() and not rental_cost_df_T.empty:
                st.subheader("📊 出租情况表")
                st.dataframe(rental_cost_df_T, use_container_width=True)
            else:
                # 调用函数，传参全用代码里真实存在的变量，100%匹配函数定义
                rental_cost_df = calc_rental_operation_table(
                    all_years=all_years,
                    is_operate=is_operate,
                    operate_year_list=operate_year_list,
                    comm_area=comm_area,
                    comm_rent_start_price=comm_rent_start_price,
                    comm_rent_increase_span=comm_rent_increase_span,
                    comm_rent_increase_rate=comm_rent_increase_rate,
                    comm_occupancy_ramp_dict=comm_occupancy_ramp_dict,
                    comm_stable_start=comm_stable_start,
                    comm_stable_end=comm_stable_end,
                    comm_occupancy_stable=comm_occupancy_stable,
                    park_count=park_count,
                    land_cost=land_cost,
                    construction_cost=construction_cost,
                    infra_cost=infra_cost,
                    other_eng_cost=other_eng_cost,
                    lease_months=lease_months if 'lease_months' in locals() else 12,
                    land_use_area=land_use_area,
                    project_input_tax=project_input_tax,
                )
                rental_cost_df_T = rental_cost_df.T

                rental_sum_rows = [
                    "商业出租收入(万元)", "房产税1(万元)", "房产税2(万元)", 
                    "运营管理费用（商业）(万元)", "运营管理费用（停车场）(万元)", 
                    "物业专项维修金(万元)", "维修费用(万元)", "空置物业服务费(万元)", 
                    "保险费用(万元)", "土地使用税(万元)", "出租营运成本合计(万元)", "销项税(万元)",
                    "增值税(一般计税)(万元)", "增值税附加(万元)", "印花税(万元)", "出租经营税金合计(万元)",
                    "出租净收入(万元)", "出租净收益现值(万元)"
                ]

                rental_cost_df_T["全周期合计(万元)"] = rental_cost_df_T.apply(
                    lambda row: round(row.sum(), 4) if row.name in rental_sum_rows else "/", axis=1
                )

                total_manage = rental_cost_df.loc[:, "运营管理费用（商业）(万元)"].sum()
                total_insurance = rental_cost_df.loc[:, "保险费用(万元)"].sum()
                total_vacancy = rental_cost_df.loc[:, "空置物业服务费(万元)"].sum()
                input_tax_total = (total_manage + total_insurance) * (0.06 / 1.06) + total_vacancy * (0.09 / 1.09) + project_input_tax
                rental_cost_df_T.loc["进项税(万元)", "全周期合计(万元)"] = round(input_tax_total, 4)

                rental_cost_df_T = rental_cost_df_T[["全周期合计(万元)"] + [col for col in rental_cost_df_T.columns if col != "全周期合计(万元)"]]

                st.subheader("📊 出租情况表")
                st.dataframe(rental_cost_df_T, use_container_width=True)
    
        if (not use_snapshot_only) and project_type == "出售类(配保房/可售型人才房等)":
            income_df["出租净收益现值(万元)"] = rental_cost_df["出租净收益现值(万元)"].fillna(0)
            income_df["总收入(万元)"] = (
                income_df["配保房销售收入(万元)"]
                + income_df["出租净收益现值(万元)"]
                + income_df["住宅租金收入(万元)"]
                + income_df["车位收入(万元)"]
                + income_df[f"{other_income_name}(万元)"]
            )
            income_df_T = income_df.T
            income_df_T["全周期合计(万元)"] = income_df_T.apply(
                lambda r: round(r.sum(), 4) if r.name in income_sum_rows else "/", axis=1
            )
            income_df_T = income_df_T[["全周期合计(万元)"] + [c for c in income_df_T.columns if c != "全周期合计(万元)"]].fillna("/")
            income_df_T = income_df_T.reindex(
                ["配保房销售收入(万元)", "出租净收益现值(万元)"] +
                [idx for idx in income_df_T.index if idx not in ["配保房销售收入(万元)", "出租净收益现值(万元)"]]
            )
        
        # --- 收入明细 ---
        st.subheader("📋 收入明细表")
        # 出售类自动隐藏指定行，非出售类正常显示
        if project_type == "出售类(配保房/可售型人才房等)": income_df_T = income_df_T.drop(["计算过程说明", "住宅租金单价(元/㎡/月)", "住宅出租率", "车位租金单价(元/个/月)", "车位出租率","商业出租收入(万元)"], errors="ignore")
        st.dataframe(income_df_T, use_container_width=True)
        
        st.markdown("---")
        
          # --- 总成本费用明细 ---
        st.subheader("💸 总成本费用明细")
        # 给总成本费用行的文字标红
        cost_styled = cost_df_T.style.apply(
            lambda x: ['color: red; font-weight: bold' if x.name == "总成本费用(不含建设期财务费用、不含税金)(万元)" else '' for _ in x],
            axis=1
        )
        st.dataframe(cost_styled, use_container_width=True)
        
        st.markdown("---")
        
        # --- 新增：还本付息明细 ---
        st.subheader("🏦 还本付息明细")
        st.dataframe(loan_df_T, use_container_width=True)
    
        st.markdown("---")
    
        if project_type != "出售类(配保房/可售型人才房等)":
            # --- 新增：税金及其附加明细 ---
            st.subheader("📝 税金及其附加明细")
            tax_df_T = tax_df.T
            tax_df_T["全周期合计(万元)"] = tax_df_T.sum(axis=1).round(4)
            tax_df_T = tax_df_T[ ["全周期合计(万元)"] + [col for col in tax_df_T.columns if col != "全周期合计(万元)"] ]
            st.dataframe(tax_df_T, use_container_width=True)
            st.markdown("---")
        
        # --- 新增：损益表明细 ---
        # --- 新增：损益表明细 ---
        st.subheader("📈 损益表明细")
        # 【修复】直接复用前面已经用最终收入算好的profit_df，确保和收入明细表100%一致
        # 仅出租型需要重新计算（出售型前面已经算好）
        is_sale = (project_type == "出售类(配保房/可售型人才房等)")
        #profit_df = calc_profit(all_years, income_df, total_cost_df, tax_df)
        if not is_sale:
            profit_df = calc_profit(all_years, income_df, total_cost_df, tax_df, is_sale_project=False)
        
        # 下面的合计、展示代码完全不动，只改上面的调用部分
        profit_df_T = profit_df.T
        # 出售型剔除税金及其附加行，出租型保持完整
        if is_sale:
            profit_sum_rows = ["总收入(万元)", "总成本费用(万元)", "利润总额(万元)", "弥补亏损(万元)", "应纳税所得额(万元)", "所得税(万元)", "净利润(万元)"]
            profit_df_T = profit_df_T.drop("税金及其附加总和(万元)", errors="ignore")
        else:
            profit_sum_rows = ["总收入(万元)", "总成本费用(万元)", "税金及其附加总和(万元)", "利润总额(万元)", "弥补亏损(万元)", "应纳税所得额(万元)", "所得税(万元)", "净利润(万元)"]
        # 全周期合计计算    
        profit_df_T["全周期合计(万元)"] = profit_df_T.apply(lambda row: round(row.sum(), 4) if row.name in profit_sum_rows else "/", axis=1)
        profit_df_T = profit_df_T[ ["全周期合计(万元)"] + [col for col in profit_df_T.columns if col != "全周期合计(万元)"] ]
        st.dataframe(profit_df_T, use_container_width=True)
    
        st.markdown("---")
    
        # --- 新增：全投资现金流量表明细 ---
        st.subheader("💵 全投资现金流量表明细")
        cf_df_T = cf_df.T
        # 合计行规则：普通行求和，累计行取最后一年的期末值（符合财务表规范）
        #cf_sum_rows = ["现金流入(万元)", "配保房销售收入(万元)", "其他收入(万元)", "商业出租收入(万元)", "回收固定资产余值(万元)","建设投资(万元)", "现金流出合计(万元)", "净现金流量(万元)", "净现值(万元)"]
        cf_sum_rows = ["现金流入(万元)", "配保房销售收入(万元)", "其他收入(万元)", "商业出租收入(万元)", "回收固定资产余值(万元)", "现金流出合计(万元)", "开发成本投资(万元)", "销售费用(万元)", "销售税金及附加(万元)", "出租经营税金(万元)", "出租营运成本(万元)", "调整所得税(万元)", "净现金流量(万元)", "净现值(万元)"] if project_type == "出售类(配保房/可售型人才房等)" else ["现金流入(万元)","建设投资(万元)", "现金流出合计(万元)", "净现金流量(万元)", "净现值(万元)"]
        cf_df_T["全周期合计/期末值"] = cf_df_T.apply(
            lambda row: round(row.sum(), 4) if row.name in cf_sum_rows 
            else (round(row.iloc[-1], 4) if "累计" in row.name else "/"), 
            axis=1
        )
        # 调整列顺序，合计列放最前面
        cf_df_T = cf_df_T[ ["全周期合计/期末值"] + [col for col in cf_df_T.columns if col != "全周期合计/期末值"] ]
        if calc_button:
            snapshot_dict = {
                "page_key": current_page_key,
                "project_type": project_type,
                "project_name": project_name,

                "total_income": total_income,
                "total_cost": total_cost,
                "total_interest": total_interest,
                "total_net_profit": total_net_profit,
                "interest_coverage_ratio": interest_coverage_ratio,
                "total_npv_sum": total_npv_sum,
                "irr_value": irr_value,

                "income_df_T": income_df_T.copy(),
                "cost_df_T": cost_df_T.copy(),
                "loan_df_T": loan_df_T.copy(),
                "profit_df_T": profit_df_T.copy(),
                "cf_df_T": cf_df_T.copy(),
                "tax_df_T": tax_df_T.copy() if 'tax_df_T' in locals() else pd.DataFrame(),
                "rental_cost_df_T": rental_cost_df_T.copy() if 'rental_cost_df_T' in locals() else pd.DataFrame(),

                # 聊天直接恢复用
                "ai_result_context": st.session_state.get("ai_result_context", {}).copy(),

                # AI模式说明恢复用
                "ai_core_input": st.session_state.get("ai_core_input", {}).copy() if st.session_state.get("ai_core_input") else {},
                "ai_params": st.session_state.get("ai_params", {}).copy() if st.session_state.get("ai_params") else {},
                "ai_similar_projects": list(st.session_state.get("ai_similar_projects", [])),
                "ai_similar_project_names": list(st.session_state.get("ai_similar_project_names", [])),
            }
            save_ai_result_snapshot(snapshot_dict)
        st.dataframe(cf_df_T, use_container_width=True)
        
        # 9. 一键下载Excel
        st.markdown("---")
        excel_file_name = f"{project_name}_财务测算结果_{datetime.now().strftime('%Y%m%d')}.csv"
        st.download_button(
            label="📥 下载完整测算表（含计算过程）",
            data=income_df_T.to_csv().encode("utf-8-sig"),
            file_name=excel_file_name,
            mime="text/csv",
            use_container_width=True
        )
        
        # ===================== 所有模式通用：结果问答 =====================
        if st.session_state.get("ai_result_context"):
            st.markdown("---")
            render_ai_chat_panel()
    except Exception as e:
        st.error(f"测算过程报错：{e}")
        st.exception(e)
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
