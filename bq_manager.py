import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import bigquery
import os
from datetime import datetime

UPLOAD_FOLDER = 'uploads'

def _log_message(message, logs=None):
    """로그 메시지를 추가합니다."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    if logs is not None:
        logs.append(log_entry)
    return log_entry

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
    logs = []
    _log_message("테이블 생성 시작", logs)
    
    try:
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
        _log_message(f"스키마 로드 완료 ({len(english_columns)}개 컬럼)", logs)

        credentials = service_account.Credentials.from_service_account_file(config['credential_path'])
        client = bigquery.Client(credentials=credentials, project=credentials.project_id)

        client.delete_table(config['bq_table_id'], not_found_ok=True)
        _log_message("기존 테이블 삭제 완료", logs)

        bq_schema = [
            bigquery.SchemaField(name=col, field_type=typ)
            for col, typ in zip(english_columns, types)
        ]
        table = bigquery.Table(config['bq_table_id'], schema=bq_schema)
        client.create_table(table)
        _log_message("테이블 생성 완료", logs)
        
        return {
            'columns_count': len(english_columns),
            'columns': english_columns,
            'logs': logs
        }
    except Exception as e:
        _log_message(f"오류: {str(e)}", logs)
        raise

def _get_sheet_data(config):
    """Google Sheets에서 헤더와 데이터를 가져옵니다."""
    logs = []
    _log_message("Google Sheets 데이터 가져오기 시작", logs)
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            config['credential_path'], 
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )
        sheet = build("sheets", "v4", credentials=credentials)

        header_result = sheet.spreadsheets().values().get(
            spreadsheetId=config['sheet_id'], 
            range=config['header_range']
        ).execute()
        header_row = header_result.get("values", [])[0]

        data_result = sheet.spreadsheets().values().get(
            spreadsheetId=config['sheet_id'], 
            range=config['data_range']
        ).execute()
        rows = data_result.get("values", [])
        _log_message(f"데이터 로드 완료 ({len(rows)}행, {len(header_row)}열)", logs)

        if not rows:
            raise ValueError("시트에 데이터가 없습니다.")

        df = pd.DataFrame(rows, columns=header_row)
        return df, logs
    except Exception as e:
        _log_message(f"오류: {str(e)}", logs)
        raise

def _preprocess_dataframe(df, config):
    """스키마에 따라 데이터프레임을 전처리합니다."""
    logs = []
    _log_message("데이터 전처리 시작", logs)
    
    try:
        schema_path = os.path.join(UPLOAD_FOLDER, config['schema_csv'])
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"스키마 파일을 찾을 수 없습니다: {config['schema_csv']}")
            
        schema_df = pd.read_csv(schema_path)
        schema_columns = list(schema_df["기존 컬럼명"])
        schema_english_columns = list(schema_df["영어 컬럼명"])
        column_types = dict(zip(schema_df["영어 컬럼명"], schema_df["데이터 타입"]))

        if list(df.columns) != schema_columns:
            raise ValueError(
                f"시트의 헤더와 스키마의 '기존 컬럼명' 순서가 일치하지 않습니다.\n"
                f"시트 헤더: {df.columns.tolist()}\n"
                f"스키마 컬럼: {schema_columns}"
            )

        new_columns = schema_english_columns
        if len(new_columns) != len(set(new_columns)):
            raise ValueError(f"영어 컬럼명에 중복이 있습니다: {new_columns}")
        
        df.columns = new_columns
        _log_message("컬럼명 변환 완료", logs)

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
                df[col] = df[col].astype(str).str.upper()
                df[col] = df[col].map({'TRUE': True, 'FALSE': False, '1': True, '0': False, 'YES': True, 'NO': False})
                df[col] = df[col].fillna(False)
            else:
                df[col] = df[col].astype(str)
        _log_message("데이터 타입 변환 완료", logs)
        
        return df, logs
    except Exception as e:
        _log_message(f"오류: {str(e)}", logs)
        raise

def append_to_bq(config):
    """Google Sheets 데이터를 BigQuery 테이블에 추가합니다."""
    logs = []
    _log_message("데이터 추가 작업 시작", logs)
    
    try:
        _validate_bq_table_id(config.get('bq_table_id'))
        
        df, sheet_logs = _get_sheet_data(config)
        logs.extend(sheet_logs)
        
        df, preprocess_logs = _preprocess_dataframe(df, config)
        logs.extend(preprocess_logs)

        bq_client = bigquery.Client.from_service_account_json(config['credential_path'])
        job = bq_client.load_table_from_dataframe(df, config['bq_table_id'])
        job.result()
        _log_message("BigQuery 업로드 완료", logs)
        
        return {
            'rows_processed': len(df),
            'columns_processed': len(df.columns),
            'logs': logs
        }
    except Exception as e:
        _log_message(f"오류: {str(e)}", logs)
        raise

def update_bq_table(config):
    """BigQuery 테이블 데이터를 Google Sheets 데이터로 덮어씁니다."""
    logs = []
    _log_message("데이터 덮어쓰기 작업 시작", logs)
    
    try:
        _validate_bq_table_id(config.get('bq_table_id'))

        df, sheet_logs = _get_sheet_data(config)
        logs.extend(sheet_logs)
        
        df, preprocess_logs = _preprocess_dataframe(df, config)
        logs.extend(preprocess_logs)
        
        bq_client = bigquery.Client.from_service_account_json(config['credential_path'])
        job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
        job = bq_client.load_table_from_dataframe(df, config['bq_table_id'], job_config=job_config)
        job.result()
        _log_message("BigQuery 덮어쓰기 완료", logs)
        
        return {
            'rows_processed': len(df),
            'columns_processed': len(df.columns),
            'logs': logs
        }
    except Exception as e:
        _log_message(f"오류: {str(e)}", logs)
        raise 