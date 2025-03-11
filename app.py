import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

from datetime import datetime

current_time = datetime.now().strftime('%y%m%d %H%M')
version = 'v1.1.0'
st.title(f'Tealiumライセンス利用状況予測システム {current_time} {version}')

uploaded_file = st.file_uploader('過去の利用データをアップロードしてください（CSV形式）', type=['csv'])

if uploaded_file is not None:
    # ファイルをバイナリで読み込む
    import io
    raw_data = uploaded_file.getvalue()
    try:
        raw_data = raw_data.decode('utf-8')
        detected_encoding = 'utf-8'
    except UnicodeDecodeError:
        raw_data = raw_data.decode('shift_jis')
        detected_encoding = 'shift_jis'
    try:
        df = pd.read_csv(io.StringIO(raw_data), on_bad_lines='skip')
        df.columns = df.columns.str.strip()  # カラム名の前後の空白を削除
        st.write('CSVのカラム:', df.columns.tolist())  # デバッグ用にカラム名を表示  # デバッグ用にカラム名を表示
    except Exception as e:
        st.error(f'CSVの読み込みに失敗しました。エラー: {str(e)}')
        st.stop()
    except Exception as e:
        st.error(f'CSVの読み込みに失敗しました。エラー: {str(e)}')
        st.write(raw_data[:500])  # エラー発生時にデータの一部を表示
        st.stop()
    except UnicodeDecodeError:
        df = pd.read_csv(BytesIO(raw_data), encoding='shift_jis', on_bad_lines='skip')
    except Exception as e:
        st.error(f'CSVの読み込みに失敗しました。エラー: {str(e)}')
        st.stop()
    except UnicodeDecodeError:
        df = pd.read_csv(uploaded_file, encoding='shift_jis', on_bad_lines='skip')
    
    # 「Grand Total」のデータのみ抽出
    if 'Profile' in df.columns:
        df = df[df['Profile'] == 'Grand Total']
    else:
        st.error('Profile列が見つかりません。正しいファイルをアップロードしてください。')
        st.stop()

    # 日付処理
    if 'Date' in df.columns:
        df['日付'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['日付'])
        df['曜日'] = df['日付'].dt.weekday
    else:
        st.error('Date列が見つかりません。正しいファイルをアップロードしてください。')
        st.stop()

    # VisitsとAll Inbound Eventsがあるかチェック
    required_columns = ['Visits', 'All Inbound Events']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f'以下の列が見つかりません: {missing_columns}。正しいファイルをアップロードしてください。')
        st.stop()
    
    # 曜日別平均値を計算
    weekday_avg = df.groupby('曜日')[required_columns].mean()
    weekday_avg.index = weekday_avg.index.astype(int)
    

    st.subheader('曜日ごとの平均値')
    st.dataframe(weekday_avg)

    # 繁忙期設定
    st.subheader('繁忙期の設定')
    busy_months = st.multiselect('繁忙期の月を選択してください', options=list(range(1, 13)), default=[3, 4, 9, 10, 12])
    busy_factor = st.slider('繁忙期の追加係数（例：1.2で20％増）', min_value=1.0, max_value=2.0, step=0.1, value=1.2)

    # 予測期間設定
    契約開始日 = st.date_input('契約開始日を選択', pd.to_datetime(df['日付'].min()))
    契約終了日 = st.date_input('契約終了日を選択', pd.to_datetime(df['日付'].max()))
    契約期間の日数 = (契約終了日 - 契約開始日).days

    # 予測データ作成
    forecast_dates = pd.date_range(start=契約開始日, end=契約終了日)
    past_df = df[df['日付'].between(pd.to_datetime(契約開始日), pd.to_datetime(契約終了日))].copy()
    forecast_df = pd.DataFrame({'曜日': forecast_dates.weekday, 'Date': forecast_dates})
    forecast_df['曜日'] = pd.to_numeric(forecast_df['曜日'], errors='coerce').fillna(0).astype(int)
    forecast_df['Visits'] = weekday_avg['Visits'].reindex(forecast_df['曜日']).values
    forecast_df['All Inbound Events'] = weekday_avg['All Inbound Events'].reindex(forecast_df['曜日']).values
    forecast_df['Omnichannel Events'] = 0  # デフォルト値
    forecast_df['平均point'] = df['Visits'].mean()  # 過去データの平均を使用
    forecast_df['Date'] = pd.to_datetime(forecast_df['Date'], errors='coerce')
    forecast_df['Date'] = pd.to_datetime(forecast_df['Date'], errors='coerce')
    forecast_df['月'] = forecast_df['Date'].dt.month
    forecast_df['予測追加係数'] = np.where(forecast_df['月'].isin(busy_months), busy_factor, 1.0)
    forecast_df['Visits'] = weekday_avg['Visits'].reindex(forecast_df['曜日']).values
    forecast_df['All Inbound Events'] = weekday_avg['All Inbound Events'].reindex(forecast_df['曜日']).values
    
    forecast_df['Date'] = pd.to_datetime(forecast_df['Date'], errors='coerce')
    forecast_df['月'] = forecast_df['Date'].dt.month

    # 予測値を季節変動を考慮して算出
    forecast_df['予測セッション'] = forecast_df.apply(lambda row: row['Visits'] if row['Date'] in past_df['日付'].values and not pd.isna(row['Visits']) else weekday_avg['Visits'].get(row['曜日'], 0) * row['予測追加係数'], axis=1)
    forecast_df['予測Event'] = forecast_df.apply(lambda row: row['All Inbound Events'] if row['Date'] in past_df['日付'].values and not pd.isna(row['All Inbound Events']) else weekday_avg['All Inbound Events'].get(row['曜日'], 0) * row['予測追加係数'], axis=1)

    st.subheader('予測結果')
    
    契約セッション年間ボリューム = st.number_input('契約セッション年間ボリューム', min_value=1, value=10000000)
    forecast_df['契約セッション'] = 契約セッション年間ボリューム / 契約期間の日数
    契約Event年間ボリューム = st.number_input('契約Event年間ボリューム', min_value=1, value=25000000)
    forecast_df['契約Event'] = 契約Event年間ボリューム / 契約期間の日数
    forecast_df['予測セッション累計'] = forecast_df['予測セッション'].cumsum()
    forecast_df['予測Event累計'] = forecast_df['予測Event'].cumsum()
    forecast_df['契約セッション累計'] = np.minimum(forecast_df['契約セッション'].cumsum(), 契約セッション年間ボリューム)
    forecast_df['契約Event累計'] = np.minimum(forecast_df['契約Event'].cumsum(), 契約Event年間ボリューム)

    past_df['契約セッション'] = 契約セッション年間ボリューム / 契約期間の日数
    past_df['契約Event'] = 契約Event年間ボリューム / 契約期間の日数
    past_df['予測セッション累計'] = past_df['Visits'].cumsum()
    past_df['予測Event累計'] = past_df['All Inbound Events'].cumsum()
    past_df['契約セッション累計'] = np.minimum(past_df['契約セッション'].cumsum(), 契約セッション年間ボリューム)
    past_df['契約Event累計'] = np.minimum(past_df['契約Event'].cumsum(), 契約Event年間ボリューム)

    combined_df = pd.concat([past_df, forecast_df], ignore_index=True)
    if 'Profile' in combined_df.columns:
        combined_df = combined_df[combined_df['Profile'] == 'Grand Total']
        combined_df = combined_df.drop(columns=['Profile'], errors='ignore')  # Profile列を削除
    if 'Profile' in combined_df.columns:
        combined_df = combined_df[combined_df['Profile'] == 'Grand Total']
    combined_df['Date'] = pd.to_datetime(combined_df['Date'], errors='coerce')
    combined_df = combined_df.dropna(subset=['Date'])  # NaT の行を削除
    combined_df['Date'] = combined_df['Date'].fillna(method='ffill')
    combined_df['Date'] = combined_df['Date'].fillna(method='ffill').dt.strftime('%Y/%m/%d')
    st.dataframe(combined_df[['曜日', 'Date', 'Visits', 'All Inbound Events', 'Omnichannel Events', '平均point', '予測追加係数', '予測セッション', '予測Event', '契約セッション', '契約Event', '予測セッション累計', '予測Event累計', '契約セッション累計', '契約Event累計']])

    # 結果をExcel形式でダウンロード
    output = BytesIO()
    combined_df.to_excel(output, index=False)
    st.download_button(label='予測結果をExcelでダウンロード', data=output.getvalue(), file_name='予測結果.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
