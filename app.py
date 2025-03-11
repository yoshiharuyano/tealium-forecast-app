import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.title('Tealiumライセンス利用状況予測システム')

uploaded_file = st.file_uploader('過去の利用データをアップロードしてください（CSV形式）', type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, encoding='utf-8')

    # 「Grand Total」のデータのみ抽出
    df = df[df['Profile'] == 'Grand Total']

    # 日付処理
    df['日付'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['日付'])
    df['曜日'] = df['日付'].dt.weekday

    # 曜日別平均値を計算
    weekday_avg = df.groupby('曜日')[['Visits', 'All Inbound Events']].mean()

    st.subheader('曜日ごとの平均値')
    st.dataframe(weekday_avg)

    # 繁忙期設定
    st.subheader('繁忙期の設定')
    busy_months = st.multiselect('繁忙期の月を選択してください', options=list(range(1, 13)), default=[3, 4, 9, 10, 12])
    busy_factor = st.slider('繁忙期の追加係数（例：1.2で20％増）', min_value=1.0, max_value=2.0, step=0.1, value=1.2)

    # 予測期間設定
    forecast_start = st.date_input('予測開始日を選択', pd.Timestamp.today())
    forecast_days = st.number_input('予測する日数', min_value=1, max_value=365, value=30)

    # 予測データ作成
    forecast_dates = pd.date_range(start=forecast_start, periods=forecast_days)
    forecast_df = pd.DataFrame({'日付': forecast_dates})
    forecast_df['曜日'] = forecast_df['日付'].dt.weekday
    forecast_df['月'] = forecast_df['日付'].dt.month

    # 予測値を季節変動を考慮して算出
    forecast_df['予測Visits'] = forecast_df.apply(
        lambda row: weekday_avg.loc[row['曜日'], 'Visits'] * busy_factor if row['月'] in busy_months else weekday_avg.loc[row['曜日'], 'Visits'], axis=1)
    forecast_df['予測Events'] = forecast_df.apply(
        lambda row: weekday_avg.loc[row['曜日'], 'All Inbound Events'] * busy_factor if row['月'] in busy_months else weekday_avg.loc[row['曜日'], 'All Inbound Events'], axis=1)

    st.subheader('予測結果')
    st.dataframe(forecast_df[['日付', '予測Visits', '予測Events']])

    # 結果をExcel形式でダウンロード
    output = BytesIO()
    forecast_df.to_excel(output, index=False)
    st.download_button(label='予測結果をExcelでダウンロード', data=output.getvalue(), file_name='予測結果.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
