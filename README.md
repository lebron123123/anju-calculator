# anju-calculator
这是一个用来进行安居房财务测算的仓库

一、“配置表”用于对不同计算规则的项目类型进行调用  
PROJECT_CONFIG{{}} 
（一）项目专属的输入框（extra_inputs）  
（二）项目在界面上多的显示特殊区域（ui_components）    
       1.if "" in current_config.get("ui_components", []): #这个来判断是否调用  
（三）项目的计算规则是什么（calc_rules）  
（四）这种项目的结果页额外显示指标（show_metrics）    

二、streamlit库应用

（一）页面显示
      st.set_page_config()网页标题  
      st.title()页面大标题
      st.subheader（）创建栏目标题
      st.selectbox（）创建下拉菜单
（二）其他功能
      st.session_state()功能盒子
      
