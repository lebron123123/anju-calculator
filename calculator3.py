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
    
    # ---------------------- 运营期年份：改为区间选择（核心优化）----------------------
    st.subheader("运营期年份（区间选择）")
    # 初始化session_state+回调函数（修复报错核心，一行排版）
    if "operate_start" not in st.session_state: st.session_state.operate_start = 2027
    if "operate_end" not in st.session_state: st.session_state.operate_end = 2029
    def sync_operate_end():
        if st.session_state.operate_end < st.session_state.operate_start: st.session_state.operate_end = st.session_state.operate_start
    
    # 界面一行展示：起始年+结束年（两列等分）
    col1, col2 = st.columns(2)
    operate_start = col1.number_input("运营期起始年", min_value=START_YEAR, max_value=END_YEAR, value=st.session_state.operate_start, step=1, key="operate_start", on_change=sync_operate_end)
    operate_end = col2.number_input("运营期结束年", min_value=operate_start, max_value=END_YEAR, value=st.session_state.operate_end, step=1, key="operate_end")
    
    # 自动生成运营期年份列表（一行）
    operate_years = list(range(operate_start, operate_end + 1))
    
    # 展示生成结果（一行）
    st.info(f"✅ 已自动生成运营期年份：{operate_years}")
    
    # 合法性校验（一行）
    if build_years and operate_start < max(build_years): st.warning(f"⚠️ 运营期起始年({operate_start})早于建设期最后一年({max(build_years)})，请检查！")

# 2. 收入计算参数
with st.expander("2. 收入计算参数", expanded=True):
    # 基础参数（一行排版）
    residential_area = st.number_input("住宅面积（㎡）", value=34330, min_value=0)
    rent_start_price = st.number_input("起始租金单价（元/㎡/月）", value=19.2, min_value=0.0, step=0.1)
    
    # ---------------------- 新增需求①：租金每X年递增Y% ----------------------
    st.subheader("📈 租金递增设置")
    col_rent1, col_rent2 = st.columns(2)
    rent_increase_span = col_rent1.number_input("租金递增跨度（年）", min_value=1, max_value=50, value=3, step=1, help="每过X年租金递增一次")
    rent_increase_rate = col_rent2.number_input("租金递增率（%）", min_value=0.0, max_value=50.0, value=2.0, step=0.1, help="每次递增的百分比")
    
    # ---------------------- 新增需求②：出租率爬坡期+稳定期 ----------------------
    st.subheader("🏢 出租率设置（爬坡期+稳定期）")
    # 先获取运营期年份作为可选范围（联动之前的operate_years）
    if 'operate_years' in locals() and operate_years:
        # 1. 爬坡期设置：让用户选年份，动态生成输入框
        ramp_years = st.multiselect("请选择爬坡期年份（从运营期年份中选）", options=operate_years, default=operate_years[:2] if len(operate_years)>=2 else operate_years)
        # 动态生成爬坡期每年的出租率输入框（一行排版）
        occupancy_ramp_dict = {}
        if ramp_years:
            col_ramp = st.columns(len(ramp_years))
            for idx, year in enumerate(ramp_years):
                occupancy_ramp_dict[year] = col_ramp[idx].number_input(f"{year}年出租率", min_value=0.0, max_value=1.0, value=0.7 if idx==0 else 0.8, step=0.01)
        
        # 2. 稳定期设置：区间选择+固定出租率
        st.markdown("---")
        col_stable1, col_stable2, col_stable3 = st.columns(3)
        # 稳定期起始年默认是爬坡期最后一年+1，且≥运营期起始年
        default_stable_start = max(ramp_years) + 1 if ramp_years else operate_years[0]
        stable_start = col_stable1.number_input("稳定期起始年", min_value=operate_years[0], max_value=operate_years[-1], value=default_stable_start, step=1)
        # 稳定期结束年默认用运营期结束年，且≥起始年
        stable_end = col_stable2.number_input("稳定期结束年", min_value=stable_start, max_value=operate_years[-1], value=operate_years[-1], step=1)
        # 稳定期固定出租率
        occupancy_stable = col_stable3.number_input("稳定期出租率", min_value=0.0, max_value=1.0, value=0.9, step=0.01)
    else:
        st.warning("⚠️ 请先在「1. 项目基本信息」中设置运营期年份！")

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




