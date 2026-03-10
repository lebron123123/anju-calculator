# ===================== 安居房财务测算计算器（微信网页版-优化）=====================
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# ===================== 页面配置（优化：更适合手机）=====================
st.set_page_config(page_title="安居房财务测算", page_icon="🏠", layout="centered")
st.title("🏠 安居房财务测算计算器")
st.markdown("---")

# ===================== 输入区（优化：手机上更易操作）=====================
st.header("📝 请输入项目数据")

# 定义年份范围（方便后续调整，可选但推荐）
START_YEAR = 2025
END_YEAR = 2200
year_options = list(range(START_YEAR, END_YEAR + 1))  # 生成2025~2200的年份列表

# 1. 项目基本信息
with st.expander("1. 项目基本信息", expanded=True):
    project_name = st.text_input("项目名称", value="安居XX项目测算（测试）")
    # 建设期年份：用生成的年份列表，默认值不变
    build_years = st.multiselect("建设期年份", options=year_options, default=[2025, 2026])
    # 运营期年份：同样用生成的年份列表，默认值不变
    
 st.subheader("运营期年份（区间选择）")
# 用columns实现起始年+结束年界面上一行展示
col1, col2 = st.columns(2)
# 运营期起始年：参数全部一行排版，界面放在第一列
with col1:
    operate_start = st.number_input("运营期起始年", min_value=START_YEAR, max_value=END_YEAR, value=2027, step=1, key="operate_start")
# 运营期结束年：参数全部一行排版，界面放在第二列
with col2:
    operate_end = st.number_input("运营期结束年", min_value=operate_start, max_value=END_YEAR, value=2029, step=1, key="operate_end")
# 自动生成运营期年份列表（一行代码）
operate_years = list(range(operate_start, operate_end + 1))
# 生成的年份列表一行展示（界面上一行）
st.info(f"✅ 已自动生成运营期年份：{operate_years}")
# 合法性校验一行展示（代码+界面都一行）
if build_years and operate_start < max(build_years):
    st.warning(f"⚠️ 运营期起始年({operate_start})早于建设期最后一年({max(build_years)})，请检查！")

# 2. 收入计算参数
with st.expander("2. 收入计算参数", expanded=True):
    residential_area = st.number_input("住宅面积（㎡）", value=34330, min_value=0)
    rent_start_price = st.number_input("起始租金单价（元/㎡/月）", value=19.2, min_value=0.0, step=0.1)
    occupancy_ramp1 = st.number_input("运营第1年出租率", value=0.7, min_value=0.0, max_value=1.0, step=0.01)
    occupancy_ramp2 = st.number_input("运营第2年出租率", value=0.8, min_value=0.0, max_value=1.0, step=0.01)
    occupancy_stable = st.number_input("稳定期出租率", value=0.9, min_value=0.0, max_value=1.0, step=0.01)

st.markdown("---")

# 3. 一键测算按钮
calc_button = st.button("🔽 一键开始测算", type="primary", use_container_width=True)

# ===================== 核心测算函数（完全复用之前的逻辑）=====================
def generate_year_list(build_yrs, operate_yrs):
    all_years = build_yrs + operate_yrs
    month_dict = {year: 0 if year in build_yrs else 12 for year in all_years}
    is_operate = {year: year in operate_yrs for year in all_years}
    return all_years, month_dict, is_operate

def calc_income(all_years, month_dict, is_operate, area, price, ramp1, ramp2, stable):
    income_df = pd.DataFrame(index=all_years)
    resi_occupancy = {}
    
    # 计算每年出租率
    for idx, year in enumerate([y for y in all_years if is_operate[y]]):
        if idx == 0:
            resi_occupancy[year] = ramp1
        elif idx == 1:
            resi_occupancy[year] = ramp2
        else:
            resi_occupancy[year] = stable
    
    # 计算每年租金
    for year in all_years:
        if not is_operate[year]:
            income_df.loc[year, "住宅租金收入(万元)"] = 0
            income_df.loc[year, "计算过程说明"] = "建设期，无收入"
        else:
            occ = resi_occupancy[year]
            months = month_dict[year]
            year_rent = area * price * occ * months / 10000
            income_df.loc[year, "住宅租金收入(万元)"] = round(year_rent, 4)
            income_df.loc[year, "计算过程说明"] = f"{area}㎡ × {price}元/㎡/月 × {occ}出租率 × {months}个月 ÷ 10000"
    
    income_df["总收入(万元)"] = income_df["住宅租金收入(万元)"]
    return income_df, resi_occupancy

# ===================== 结果展示区（优化：手机上更易查看）=====================
if calc_button:
    # 1. 后台执行测算
    all_years, month_dict, is_operate = generate_year_list(build_years, operate_years)
    income_df, resi_occupancy = calc_income(
        all_years, month_dict, is_operate,
        residential_area, rent_start_price,
        occupancy_ramp1, occupancy_ramp2, occupancy_stable
    )
    
    # 2. 计算最终核心指标
    total_income = round(income_df["总收入(万元)"].sum(), 2)
    
    # 3. 展示结果
    st.header("📊 测算结果")
    st.markdown("---")
    
    # --- 第一个区域：最终财务结果（优化：手机上更醒目）---
    st.subheader("🎯 最终财务结果汇总")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("项目全周期总收入", f"{total_income} 万元")
    with col2:
        st.metric("项目运营年限", f"{len(operate_years)} 年")
    
    st.markdown("---")
    
    # --- 第二个区域：每一步的具体计算过程表 ---
    st.subheader("📋 每一步具体计算过程明细")
    st.dataframe(income_df, use_container_width=True)
    
    # 4. 一键下载Excel（优化：微信里也能正常下载）
    st.markdown("---")
    excel_file_name = f"{project_name}_财务测算结果_{datetime.now().strftime('%Y%m%d')}.csv"
    st.download_button(
        label="📥 下载完整测算表（含计算过程）",
        data=income_df.to_csv().encode("utf-8-sig"),
        file_name=excel_file_name,
        mime="text/csv",
        use_container_width=True

    )

