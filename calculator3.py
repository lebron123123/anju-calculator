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

# 1. 项目基本信息（完整正确版，确保build_years、operate_years全局可访问）
with st.expander("1. 项目基本信息", expanded=True):
    project_name = st.text_input("项目名称", value="安居XX项目测算（测试）")
    # 【新增：房源类型选择，仅此一行】
    house_type = st.radio("房源类型", options=["公租房", "保租房"], index=0, horizontal=True, help="用于匹配装修重置费计算规则")
    # 建设期年份：原有代码完全不动
    build_years = st.multiselect("建设期年份", options=year_options, default=[2025, 2026])
    
    # ---------------------- 运营期年份区间选择（修复警告+缩进正确版）----------------------
    st.subheader("运营期年份（区间选择）")
    # 初始化session_state（仅第一次运行设置默认值）
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
    
    # ---------------------- 车位出租率设置（爬坡期+稳定期，缩进完全匹配）----------------------
    st.markdown("---")
    st.subheader("🚗 车位出租率设置（爬坡期+稳定期）")
    if 'operate_years' in locals() and operate_years:
        # 车位爬坡期设置
        park_ramp_years = st.multiselect("请选择车位爬坡期年份（从运营期年份中选）", options=operate_years, default=operate_years[:2] if len(operate_years)>=2 else operate_years)
        park_occupancy_ramp_dict = {}
        if park_ramp_years:
            col_park_ramp = st.columns(len(park_ramp_years))
            for idx, year in enumerate(park_ramp_years):
                park_occupancy_ramp_dict[year] = col_park_ramp[idx].number_input(f"车位{year}年出租率", min_value=0.0, max_value=1.0, value=0.7 if idx==0 else 0.8, step=0.01)
        
        # 车位稳定期设置
        st.markdown("---")
        col_park_stable1, col_park_stable2, col_park_stable3 = st.columns(3)
        park_default_stable_start = max(park_ramp_years) + 1 if park_ramp_years else operate_years[0]
        park_stable_start = col_park_stable1.number_input("车位稳定期起始年", min_value=operate_years[0], max_value=operate_years[-1], value=park_default_stable_start, step=1)
        park_stable_end = col_park_stable2.number_input("车位稳定期结束年", min_value=park_stable_start, max_value=operate_years[-1], value=operate_years[-1], step=1)
        park_occupancy_stable = col_park_stable3.number_input("车位稳定期出租率", min_value=0.0, max_value=1.0, value=0.9, step=0.01)
    else:
        st.warning("⚠️ 请先在「1. 项目基本信息」中设置运营期年份！")
        park_occupancy_ramp_dict, park_stable_start, park_stable_end, park_occupancy_stable = {}, 0, 0, 0
    
    # ---------------------- 其他收入设置（自定义名称+仅首年计入）----------------------
    st.markdown("---")
    st.subheader("📦 其他收入设置")
    col_other1, col_other2 = st.columns(2)
    other_income_name = col_other1.text_input("其他收入名称", value="其他收入")
    other_income_total = col_other2.number_input(f"{other_income_name}总额（万元）", min_value=0.0, value=0.0, step=10.0)

st.markdown("---")

# 3. 总成本费用参数
with st.expander("3. 总成本费用参数", expanded=True):
    st.subheader("💰 经营成本核心参数")
    col_cost1, col_cost2, col_cost3, col_cost4 = st.columns(4)
    manage_coeff = col_cost1.number_input("管理系数", min_value=0.0, value=1.92, step=0.01, help="1.92×区域系数")
    total_build_area = col_cost2.number_input("总建筑面积（㎡）", min_value=0, value=50000, step=100)
    residential_decoration_cost = col_cost3.number_input("住宅精装修工程费（万元）", min_value=0.0, value=5000.0, step=100.0)
    total_investment = col_cost4.number_input("总投资（万元）", min_value=0.0, value=50000.0, step=1000.0)

    # ---------------------- 新增：银行借款与还本付息参数 ----------------------
    st.markdown("---")
    st.subheader("🏦 银行借款与还本付息参数")
    # 基础参数
    col_loan1, col_loan2, col_loan3 = st.columns(3)
    loan_annual_rate = col_loan1.number_input("借款年利率（%）", min_value=0.0, max_value=20.0, value=3.0, step=0.1)
    first_repay_ratio = col_loan2.number_input("首次还款比例（%）", min_value=0.0, max_value=100.0, value=3.0, step=0.1, help="运营期第一年还本额=借款总额×该比例")
    repay_increase_rate = col_loan3.number_input("每年还款递增率（%）", min_value=0.0, max_value=50.0, value=4.5, step=0.1, help="每年还本额较上年的递增比例")

    # 银行借款计划（动态输入，和出租率操作逻辑一致）
    st.markdown("#### 银行借款计划")
    loan_available_years = sorted(list(set(build_years + operate_years)))
    loan_years = st.multiselect("请选择有借款的年份", options=loan_available_years, default=build_years if build_years else [])
    loan_plan_dict = {}
    if loan_years:
        col_loan_year = st.columns(len(loan_years))
        for idx, year in enumerate(loan_years):
            loan_plan_dict[year] = col_loan_year[idx].number_input(f"{year}年借款额（万元）", min_value=0.0, value=0.0, step=100.0)
    
# 4. 一键测算按钮
calc_button = st.button("🔽 一键开始测算", type="primary", use_container_width=True)

# ===================== 核心测算函数（仅加车位+其他收入逻辑，无其他改动）=====================
# ===================== 核心测算函数（极简修改版，完全匹配需求）=====================
def generate_year_list(build_yrs, operate_yrs):
    all_years = sorted(list(set(build_yrs + operate_yrs)))
    month_dict = {year: 0 if year in build_yrs else 12 for year in all_years}
    is_operate = {year: year in operate_yrs for year in all_years}
    return all_years, month_dict, is_operate

def calc_income(all_years, month_dict, is_operate, area, price, increase_span, increase_rate, occupancy_ramp_dict, stable_start, stable_end, stable_occ, park_count, park_price, park_ratio, park_occupancy_ramp_dict, park_stable_start, park_stable_end, park_stable_occ, other_name, other_total):
    income_df = pd.DataFrame(index=all_years)
    resi_occupancy, resi_rent_price, park_occupancy, park_rent_price = {}, {}, {}, {}
    operate_year_list = [y for y in all_years if is_operate[y]]
    
    # 1. 计算住宅每年出租率（原有逻辑完全不动）
    for year in operate_year_list:
        if year in occupancy_ramp_dict: resi_occupancy[year] = occupancy_ramp_dict[year]
        elif stable_start <= year <= stable_end: resi_occupancy[year] = stable_occ
        else: resi_occupancy[year] = 0.0
    
    # 2. 计算车位每年出租率（原有逻辑完全不动）
    for year in operate_year_list:
        if year in park_occupancy_ramp_dict: park_occupancy[year] = park_occupancy_ramp_dict[year]
        elif park_stable_start <= year <= park_stable_end: park_occupancy[year] = park_stable_occ
        else: park_occupancy[year] = 0.0
    
    # 3. 计算租金单价（极简修改：住宅正常递增，车位固定起始价不递增）
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
            income_df.loc[year, "计算过程说明"] = "建设期，无收入"
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
            income_df.loc[year, "住宅租金单价(元/㎡/月)"] = round(resi_rent, 2)
            income_df.loc[year, "住宅出租率"] = round(resi_occ, 4)
            income_df.loc[year, "住宅租金收入(万元)"] = round(resi_year_rent, 4)
            income_df.loc[year, "车位租金单价(元/个/月)"] = round(park_rent, 2)
            income_df.loc[year, "车位出租率"] = round(park_occ, 4)
            income_df.loc[year, "车位收入(万元)"] = round(park_year_rent, 4)
            income_df.loc[year, f"{other_name}(万元)"] = round(other_year_rent, 4)
            income_df.loc[year, "计算过程说明"] = f"住宅:{area}×{round(resi_rent,2)}×{round(resi_occ,4)}×{resi_months}/10000 + 车位:{park_count}×{round(park_rent,2)}×{round(park_occ,4)}×{park_months}×{park_ratio}/10000 + {other_name}:{round(other_year_rent,4)}"
    
    # 总收入汇总
    income_df["总收入(万元)"] = income_df["住宅租金收入(万元)"] + income_df["车位收入(万元)"] + income_df[f"{other_name}(万元)"]
    return income_df, resi_occupancy, resi_rent_price
  
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
def calc_loan_repayment(all_years, operate_start_year, loan_plan_dict, annual_rate, first_repay_ratio, repay_increase_rate):
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
    end_loan_last = 0  # 上一年期末借款余额，迭代初始值
    last_repay_principal = 0  # 上一年的还本额，用于递增计算
    is_operate_start = False  # 标记是否进入运营期
    repay_principal_plan = {}  # 预计算每年的计划还本额

    # 第一步：预计算每年的计划还本额（运营期开始按规则递增）
    for year in all_years:
        if year >= operate_start_year:
            if not is_operate_start:
                # 运营期第一年，首次还本=总借款×约定比例
                repay_principal = total_loan * first_repay_rate
                is_operate_start = True
            else:
                # 后续年份，按递增率计算还本额
                repay_principal = last_repay_principal * (1 + increase_rate)
            repay_principal_plan[year] = repay_principal
            last_repay_principal = repay_principal
        else:
            # 建设期不还本
            repay_principal_plan[year] = 0.0

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
        repay_principal = min(plan_repay, max_repayable)
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

# ===================== 结果展示区 =====================
if calc_button:
    # 前置校验，避免参数缺失报错
    if not operate_years: st.error("❌ 请先在「1. 项目基本信息」中设置运营期年份！"); st.stop()
    if not occupancy_ramp_dict: st.error("❌ 请先设置住宅爬坡期年份及对应出租率！"); st.stop()
    if stable_start > stable_end: st.error("❌ 住宅稳定期起始年不能晚于结束年！"); st.stop()
    if not loan_plan_dict: st.warning("⚠️ 未设置银行借款计划，财务费用将为0")
    
    # 1. 基础年份数据生成
    all_years, month_dict, is_operate = generate_year_list(build_years, operate_years)
    operate_start_year = operate_years[0]  # 运营期起始年，用于还款判断
    
    # 2. 收入测算（原有逻辑完全不变）
    income_df, resi_occupancy, resi_rent_price = calc_income(
        all_years, month_dict, is_operate,
        residential_area, rent_start_price,
        rent_increase_span, rent_increase_rate,
        occupancy_ramp_dict, stable_start, stable_end, occupancy_stable,
        park_count, park_rent_start_price, park_income_ratio,
        park_occupancy_ramp_dict, park_stable_start, park_stable_end, park_occupancy_stable,
        other_income_name, other_income_total
    )
    
    # 3. 经营成本测算
    park_income_dict = income_df["车位收入(万元)"].to_dict()
    operating_cost_df = calc_operating_cost(
        all_years, month_dict, is_operate,
        residential_area, resi_occupancy, resi_rent_price,
        park_income_dict, total_build_area, manage_coeff,
        residential_decoration_cost, house_type, total_investment, operate_years
    )
    
    # 4. 还本付息与财务费用测算
    loan_df, financial_cost_dict = calc_loan_repayment(
        all_years, operate_start_year,
        loan_plan_dict, loan_annual_rate,
        first_repay_ratio, repay_increase_rate
    )
    
    # 5. 生成总成本费用表（经营成本+财务费用）
    total_cost_df = operating_cost_df.copy()
    total_cost_df["财务费用(万元)"] = total_cost_df.index.map(lambda y: round(financial_cost_dict.get(y, 0.0), 4))
    total_cost_df["总成本费用(万元)"] = round(total_cost_df["经营成本(万元)"] + total_cost_df["财务费用(万元)"], 4)
    
    # 6. 统一给所有表格加「全周期合计列」（放在第二列，和之前格式完全一致）
    # --- 收入表处理 ---
    income_df_T = income_df.T
    income_sum_rows = ["住宅租金收入(万元)", "车位收入(万元)", f"{other_income_name}(万元)", "总收入(万元)"]
    income_df_T["全周期合计(万元)"] = income_df_T.apply(
        lambda row: round(row.sum(), 4) if row.name in income_sum_rows else "/", axis=1
    )
    income_df_T = income_df_T[ ["全周期合计(万元)"] + [col for col in income_df_T.columns if col != "全周期合计(万元)"] ]
    income_df_T = income_df_T.fillna("/")

    # --- 总成本费用表处理 ---
    cost_df_T = total_cost_df.T
    cost_df_T["全周期合计(万元)"] = cost_df_T.sum(axis=1).round(4)
    cost_df_T = cost_df_T[ ["全周期合计(万元)"] + [col for col in cost_df_T.columns if col != "全周期合计(万元)"] ]

    # --- 还本付息表处理 ---
    loan_df_T = loan_df.T
    loan_df_T["全周期合计(万元)"] = loan_df_T.sum(axis=1).round(4)
    # 期初/期末借款的合计无意义，填/
    loan_no_sum_rows = ["期初借款本金(万元)", "期末借款累计(万元)"]
    loan_df_T.loc[:, "全周期合计(万元)"] = loan_df_T.apply(
        lambda row: "/" if row.name in loan_no_sum_rows else row["全周期合计(万元)"], axis=1
    )
    loan_df_T = loan_df_T[ ["全周期合计(万元)"] + [col for col in loan_df_T.columns if col != "全周期合计(万元)"] ]

    # 7. 计算最终核心指标
    total_income = round(income_df["总收入(万元)"].sum(), 2)
    total_cost = round(total_cost_df["总成本费用(万元)"].sum(), 2)
    total_interest = round(loan_df["本期付息(万元)"].sum(), 2)
    net_profit = round(total_income - total_cost, 2)
    
    # 8. 页面结果展示
    st.header("📊 测算结果")
    st.markdown("---")
    
    # --- 核心指标汇总 ---
    st.subheader("🎯 最终财务结果汇总")
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("项目全周期总收入", f"{total_income} 万元")
    with col2: st.metric("项目全周期总成本费用", f"{total_cost} 万元")
    with col3: st.metric("项目全周期总付息", f"{total_interest} 万元")
    with col4: st.metric("项目全周期净利润", f"{net_profit} 万元")
    
    st.markdown("---")
    
    # --- 收入明细 ---
    st.subheader("📋 收入明细")
    st.dataframe(income_df_T, use_container_width=True)
    
    st.markdown("---")
    
    # --- 总成本费用明细 ---
    st.subheader("💸 总成本费用明细")
    st.dataframe(cost_df_T, use_container_width=True)
    
    st.markdown("---")
    
    # --- 新增：还本付息明细 ---
    st.subheader("🏦 还本付息明细")
    st.dataframe(loan_df_T, use_container_width=True)
    
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
    




















