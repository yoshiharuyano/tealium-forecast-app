import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import chardet

st.title('Tealiumライセンス利用状況予測システム 2503111819')

uploaded_file = st.file_uploader('過去の利用データをアップロードしてください（CSV形式）', type=['csv'])

if uploaded_file is not None:
    # ファイルのバイトデータを取得し、エンコーディングを自動判定
    raw_data = uploaded_file.read()
    detected_encoding = chardet.detect(raw_data)['encoding']
    
    # デコードしてDataFrameとして読み込む
    try:
        df = pd.read_csv(BytesIO(raw_data), encoding=detected_encoding)
    except Exception as e:
        st.error(f'CSVファイルの読み込みに失敗しました: {str(e)}')

    # 「Grand Total」のデータのみ抽出
    if 'Profile' in df.columns:
        df = df[df['Profile'] == 'Grand Total']
    else:
        st.error('Profile列が見つかりません。正しいファイルをアップロードしてください。')

    # 日付処理
    if 'Date' in df.columns:
        df['日付'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['日付'])
        df['曜日'] = df['日付'].dt.weekday
    else:
        st.error('Date列が見つかりません。正しいファイルをアップロードしてください。')

    # VisitsとAll Inbound Eventsがあるかチェック
    required_columns = ['Visits', 'All Inbound Events']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f'以下の列が見つかりません: {missing_columns}。正しいファイルをアップロードしてください。')
    else:
        # 曜日別平均値を計算
        weekday_avg = df.groupby('曜日')[required_columns].mean()

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
        for col in required_columns:
            forecast_df[f'予測{col}'] = forecast_df.apply(
                lambda row: weekday_avg.loc[row['曜日'], col] * busy_factor if row['月'] in busy_months else weekday_avg.loc[row['曜日'], col], axis=1)

        st.subheader('予測結果')
        st.dataframe(forecast_df[['日付'] + [f'予測{col}' for col in required_columns]])

        # 結果をExcel形式でダウンロード
        output = BytesIO()
        forecast_df.to_excel(output, index=False)
        st.download_button(label='予測結果をExcelでダウンロード', data=output.getvalue(), file_name='予測結果.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
