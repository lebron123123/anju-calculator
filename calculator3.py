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
        # 给变量赋默认值，避免NameError
        occupancy_ramp_dict, stable_start, stable_end, occupancy_stable = {}, 0, 0, 0

    # ---------------------- 新增：车位收入（逻辑同住宅，仅加特有参数）----------------------
    st.markdown("---")
    st.subheader("🚗 车位收入设置")
    col_park1, col_park2, col_park3 = st.columns(3)
    park_count = col_park1.number_input("车位个数", min_value=0, value=500, step=1)
    park_rent_start_price = col_park2.number_input("车位起始租金单价（元/个/月）", min_value=0.0, value=300.0, step=10.0)
    park_income_ratio = col_park3.number_input("车位实际收入系数", min_value=0.0, max_value=1.0, value=0.5, step=0.01, help="比如50%填0.5")
        
    # ---------------------- 新增：其他收入（仅总额）----------------------
    st.markdown("---")
    st.subheader("📦 其他收入设置")
    other_income_total = st.number_input("其他收入总额（万元）", min_value=0.0, value=0.0, step=10.0, help="项目全周期其他收入总和")

st.markdown("---")

# 3. 一键测算按钮
calc_button = st.button("🔽 一键开始测算", type="primary", use_container_width=True)

# ===================== 核心测算函数（仅加车位+其他收入逻辑，无其他改动）=====================
def calc_income(all_years, month_dict, is_operate, area, price, increase_span, increase_rate, occupancy_ramp_dict, stable_start, stable_end, stable_occ, park_count, park_price, park_ratio, other_total):
    income_df = pd.DataFrame(index=all_years)
    resi_occupancy, resi_rent_price, park_occupancy, park_rent_price = {}, {}, {}, {}
    operate_year_list = [y for y in all_years if is_operate[y]]
    operate_years_count = len(operate_year_list)
    
    # 1. 计算每年出租率（住宅+车位共用同一套出租率逻辑）
    for year in operate_year_list:
        if year in occupancy_ramp_dict: resi_occupancy[year] = park_occupancy[year] = occupancy_ramp_dict[year]
        elif stable_start <= year <= stable_end: resi_occupancy[year] = park_occupancy[year] = stable_occ
        else: resi_occupancy[year] = park_occupancy[year] = 0.0
    
    # 2. 计算每年租金单价（住宅+车位共用同一套递增逻辑）
    for idx, year in enumerate(operate_year_list):
        increase_times = idx // increase_span
        resi_rent_price[year] = price * (1 + increase_rate / 100) ** increase_times
        park_rent_price[year] = park_price * (1 + increase_rate / 100) ** increase_times
    
    # 3. 计算每年收入（住宅+车位+其他）
    for year in all_years:
        if not is_operate[year]:
            income_df.loc[year, "住宅租金收入(万元)"] = 0
            income_df.loc[year, "车位收入(万元)"] = 0
            income_df.loc[year, "其他收入(万元)"] = 0
            income_df.loc[year, "计算过程说明"] = "建设期，无收入"
        else:
            # 住宅收入
            resi_occ, resi_months, resi_rent = resi_occupancy[year], month_dict[year], resi_rent_price[year]
            resi_year_rent = area * resi_rent * resi_occ * resi_months / 10000
            # 车位收入
            park_occ, park_months, park_rent = park_occupancy[year], month_dict[year], park_rent_price[year]
            park_year_rent = park_count * park_rent * park_occ * park_months * park_ratio / 10000
            # 其他收入（按运营期平均分配）
            other_year_rent = other_total / operate_years_count if operate_years_count > 0 else 0
            
            # 填入表格
            income_df.loc[year, "住宅租金单价(元/㎡/月)"] = round(resi_rent, 2)
            income_df.loc[year, "住宅出租率"] = round(resi_occ, 4)
            income_df.loc[year, "住宅租金收入(万元)"] = round(resi_year_rent, 4)
            income_df.loc[year, "车位租金单价(元/个/月)"] = round(park_rent, 2)
            income_df.loc[year, "车位出租率"] = round(park_occ, 4)
            income_df.loc[year, "车位收入(万元)"] = round(park_year_rent, 4)
            income_df.loc[year, "其他收入(万元)"] = round(other_year_rent, 4)
            income_df.loc[year, "计算过程说明"] = f"住宅:{area}×{round(resi_rent,2)}×{round(resi_occ,4)}×{resi_months}/10000 + 车位:{park_count}×{round(park_rent,2)}×{round(park_occ,4)}×{park_months}×{park_ratio}/10000 + 其他:{round(other_year_rent,4)}"
    
    income_df["总收入(万元)"] = income_df["住宅租金收入(万元)"] + income_df["车位收入(万元)"] + income_df["其他收入(万元)"]
    return income_df, resi_occupancy

# ===================== 结果展示区（修复传参错误）=====================
if calc_button:
    # 前置校验，避免参数缺失报错
    if not operate_years: st.error("❌ 请先在「1. 项目基本信息」中设置运营期年份！"); st.stop()
    if not occupancy_ramp_dict: st.error("❌ 请先设置爬坡期年份及对应出租率！"); st.stop()
    if stable_start > stable_end: st.error("❌ 稳定期起始年不能晚于结束年！"); st.stop()

    # 1. 后台执行测算（仅加新增的4个参数，无其他改动）
    all_years, month_dict, is_operate = generate_year_list(build_years, operate_years)
    income_df, resi_occupancy = calc_income(
        all_years, month_dict, is_operate,
        residential_area, rent_start_price,
        rent_increase_span, rent_increase_rate,
        occupancy_ramp_dict, stable_start, stable_end, occupancy_stable,
        park_count, park_rent_start_price, park_income_ratio, other_income_total  # 仅加这4个新参数
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


