import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import bigquery
import os

UPLOAD_FOLDER = 'uploads'

def _validate_bq_table_id(table_id):
    """BigQuery 테이블 ID가 'project.dataset.table' 형식인지 검증합니다."""
    if not table_id or len(table_id.split('.')) != 3:
        raise ValueError(
            f"BigQuery Table ID 형식이 올바르지 않습니다. "
            f"'project.dataset.table' 형식이어야 합니다. "
            f"입력값: '{table_id}'"
        )

def create_bq_table(config):
    """BigQuery 테이블을 생성합니다."""
    _validate_bq_table_id(config.get('bq_table_id'))
    
    schema_path = os.path.join(UPLOAD_FOLDER, config['schema_csv'])
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"스키마 파일을 찾을 수 없습니다: {config['schema_csv']}")
        
    schema_df = pd.read_csv(schema_path)
    required_columns = {"기존 컬럼명", "영어 컬럼명", "데이터 타입"}
    if not required_columns.issubset(set(schema_df.columns)):
        missing = required_columns - set(schema_df.columns)
        raise ValueError(f"스키마 CSV에 누락된 컬럼이 있습니다: {missing}")

    english_columns = schema_df["영어 컬럼명"].tolist()
    types = schema_df["데이터 타입"].tolist()

    credentials = service_account.Credentials.from_service_account_file(config['credential_path'])
    client = bigquery.Client(credentials=credentials, project=credentials.project_id)

    client.delete_table(config['bq_table_id'], not_found_ok=True)

    bq_schema = [
        bigquery.SchemaField(name=col, field_type=typ)
        for col, typ in zip(english_columns, types)
    ]
    table = bigquery.Table(config['bq_table_id'], schema=bq_schema)
    client.create_table(table)
    
    return {
        'columns_count': len(english_columns),
        'columns': english_columns
    }


def _get_sheet_data(config):
    """Google Sheets에서 헤더와 데이터를 가져옵니다."""
    credentials = service_account.Credentials.from_service_account_file(
        config['credential_path'], 
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    sheet = build("sheets", "v4", credentials=credentials)

    # 헤더 가져오기
    header_result = sheet.spreadsheets().values().get(
        spreadsheetId=config['sheet_id'], 
        range=config['header_range']
    ).execute()
    header_row = header_result.get("values", [])[0]

    # 데이터 가져오기
    data_result = sheet.spreadsheets().values().get(
        spreadsheetId=config['sheet_id'], 
        range=config['data_range']
    ).execute()
    rows = data_result.get("values", [])

    if not rows:
        raise ValueError("시트에 데이터가 없습니다.")

    return pd.DataFrame(rows, columns=header_row)


def _preprocess_dataframe(df, config):
    """스키마에 따라 데이터프레임을 전처리합니다."""
    schema_path = os.path.join(UPLOAD_FOLDER, config['schema_csv'])
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"스키마 파일을 찾을 수 없습니다: {config['schema_csv']}")
        
    schema_df = pd.read_csv(schema_path)
    column_map = dict(zip(schema_df["기존 컬럼명"], schema_df["영어 컬럼명"]))
    column_types = dict(zip(schema_df["영어 컬럼명"], schema_df["데이터 타입"]))
    ordered_columns = list(column_map.values())
    
    # 컬럼 변환 및 순서 정리
    df.rename(columns=column_map, inplace=True)
    df = df[[col for col in ordered_columns if col in df.columns]]

    # 타입 변환
    for col, dtype in column_types.items():
        if col not in df.columns:
            continue
        if dtype == "INTEGER":
            df[col] = df[col].astype(str).str.replace(",", "")
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif dtype == "FLOAT":
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif dtype == "DATE":
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        elif dtype == "DATETIME":
            df[col] = pd.to_datetime(df[col], errors="coerce")
        elif dtype == "TIME":
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.time
        else:
            df[col] = df[col].astype(str)
            
    return df

def append_to_bq(config):
    """Google Sheets 데이터를 BigQuery 테이블에 추가합니다."""
    _validate_bq_table_id(config.get('bq_table_id'))
    
    df = _get_sheet_data(config)
    df = _preprocess_dataframe(df, config)

    bq_client = bigquery.Client.from_service_account_json(config['credential_path'])
    job = bq_client.load_table_from_dataframe(df, config['bq_table_id'])
    job.result()
    
    return {
        'rows_processed': len(df),
        'columns_processed': len(df.columns)
    }

def update_bq_table(config):
    """BigQuery 테이블 데이터를 Google Sheets 데이터로 덮어씁니다."""
    _validate_bq_table_id(config.get('bq_table_id'))

    df = _get_sheet_data(config)
    df = _preprocess_dataframe(df, config)
    
    bq_client = bigquery.Client.from_service_account_json(config['credential_path'])
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    job = bq_client.load_table_from_dataframe(df, config['bq_table_id'], job_config=job_config)
    job.result()
    
    return {
        'rows_processed': len(df),
        'columns_processed': len(df.columns)
    } 