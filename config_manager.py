from database import db, Setting

def get_all_settings():
    """DB에 저장된 모든 설정을 불러옵니다."""
    return Setting.query.order_by(Setting.title).all()

def get_setting_by_id(setting_id):
    """ID로 특정 설정을 불러옵니다."""
    return Setting.query.get(setting_id)

def add_setting(data):
    """새로운 설정을 DB에 추가합니다."""
    new_setting = Setting(
        title=data.get('title'),
        sheet_id=data.get('sheet_id'),
        header_range=data.get('header_range'),
        data_range=data.get('data_range'),
        bq_table_id=data.get('bq_table_id'),
        schema_csv=data.get('schema_csv', 'schema_definition.csv')
    )
    db.session.add(new_setting)
    db.session.commit()
    return new_setting

def update_setting(setting_id, data):
    """기존 설정을 업데이트합니다."""
    setting = get_setting_by_id(setting_id)
    if setting:
        setting.title = data.get('title')
        setting.sheet_id = data.get('sheet_id')
        setting.header_range = data.get('header_range')
        setting.data_range = data.get('data_range')
        setting.bq_table_id = data.get('bq_table_id')
        setting.schema_csv = data.get('schema_csv', 'schema_definition.csv')
        db.session.commit()
    return setting

def delete_setting(setting_id):
    """설정을 삭제합니다."""
    setting = get_setting_by_id(setting_id)
    if setting:
        db.session.delete(setting)
        db.session.commit()
        return True
    return False 