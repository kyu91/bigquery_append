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
    schema_columns = list(schema_df["기존 컬럼명"])
    schema_english_columns = list(schema_df["영어 컬럼명"])
    column_types = dict(zip(schema_df["영어 컬럼명"], schema_df["데이터 타입"]))

    # 1. 시트 헤더와 스키마 컬럼명(한글) 순서 일치 검사
    if list(df.columns) != schema_columns:
        raise ValueError(
            f"시트의 헤더와 스키마의 '기존 컬럼명' 순서가 일치하지 않습니다.\n"
            f"시트 헤더: {df.columns.tolist()}\n"
            f"스키마 컬럼: {schema_columns}"
        )

    # 2. 순서대로 한글 컬럼명 → 영어 컬럼명으로 변환
    new_columns = schema_english_columns  # 스키마의 영어 컬럼명 순서 그대로 사용
    
    # 3. 영어 컬럼명 중복 체크
    if len(new_columns) != len(set(new_columns)):
        raise ValueError(f"영어 컬럼명에 중복이 있습니다: {new_columns}")
    
    df.columns = new_columns

    # 4. 타입 변환
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
        elif dtype == "BOOL":
            # 불린 값으로 변환 (True/False, 1/0, "TRUE"/"FALSE" 등)
            df[col] = df[col].astype(str).str.upper()
            df[col] = df[col].map({'TRUE': True, 'FALSE': False, '1': True, '0': False, 'YES': True, 'NO': False})
            df[col] = df[col].fillna(False)  # 매핑되지 않은 값은 False로 처리
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