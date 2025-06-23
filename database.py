from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Setting(db.Model):
    """설정값을 저장하는 데이터베이스 모델"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, unique=True)
    sheet_id = db.Column(db.String(100), nullable=False)
    header_range = db.Column(db.String(100), nullable=False)
    data_range = db.Column(db.String(100), nullable=False)
    bq_table_id = db.Column(db.String(200), nullable=False)
    schema_csv = db.Column(db.String(100), default='schema_definition.csv')
    
    def to_dict(self):
        """모델 객체를 딕셔너리로 변환합니다."""
        return {
            'id': self.id,
            'title': self.title,
            'sheet_id': self.sheet_id,
            'header_range': self.header_range,
            'data_range': self.data_range,
            'bq_table_id': self.bq_table_id,
            'schema_csv': self.schema_csv,
            'credential_path': 'credentials.json' # 고정값
        } 