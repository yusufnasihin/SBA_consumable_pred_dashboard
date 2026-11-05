import streamlit as st
# Page Setup
stock = st.Page(
    page='pages/1_stock.py',
    title='Stock Dashboard',
    icon='🗃️',
    default=True
)
trans_log = st.Page(
    page='pages/2_transaction_log.py',
    title='Transaction Log',
    icon='📝'
)
pred = st.Page(
    page='pages/3_sba_pred.py',
    title='Prediction',
    icon='📊'
)
pg = st.navigation(pages=[stock, trans_log, pred])
pg.run()