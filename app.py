from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import traceback
import os
from werkzeug.utils import secure_filename
import markdown

import bq_manager
import config_manager
from database import db

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-super-secret-key-that-is-long-and-random'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///settings.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db.init_app(app)

with app.app_context():
    db.create_all()
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

def get_schema_files():
    """uploads 폴더에 있는 스키마 파일 목록을 반환합니다."""
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        return []
    return [f for f in os.listdir(upload_folder) if f.endswith('.csv')]

# --- Page Routes ---

@app.route('/')
def jobs_page():
    """작업 페이지 (메인 페이지)"""
    settings = config_manager.get_all_settings()
    return render_template('jobs.html', settings=settings, schema_files=get_schema_files())

@app.route('/settings')
def settings_list_page():
    """설정 관리 페이지"""
    settings = config_manager.get_all_settings()
    return render_template('settings_list.html', settings=settings)

@app.route('/settings/new', methods=['GET', 'POST'])
def new_setting_page():
    """새 설정 추가 페이지"""
    if request.method == 'POST':
        try:
            config_manager.add_setting(request.form)
            flash('새로운 설정이 성공적으로 저장되었습니다.', 'success')
            return redirect(url_for('settings_list_page'))
        except Exception as e:
            flash(f'저장 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return render_template('settings_form.html', 
                           form_title="새 설정 추가", 
                           setting=None,
                           schema_files=get_schema_files())

@app.route('/settings/edit/<int:setting_id>', methods=['GET', 'POST'])
def edit_setting_page(setting_id):
    """기존 설정 수정 페이지"""
    setting = config_manager.get_setting_by_id(setting_id)
    if not setting:
        flash('해당 설정을 찾을 수 없습니다.', 'error')
        return redirect(url_for('settings_list_page'))
    
    if request.method == 'POST':
        try:
            config_manager.update_setting(setting_id, request.form)
            flash('설정이 성공적으로 업데이트되었습니다.', 'success')
            return redirect(url_for('settings_list_page'))
        except Exception as e:
            flash(f'업데이트 중 오류가 발생했습니다: {str(e)}', 'error')

    return render_template('settings_form.html', 
                           form_title="설정 수정", 
                           setting=setting,
                           schema_files=get_schema_files())

@app.route('/settings/delete/<int:setting_id>', methods=['POST'])
def delete_setting_action(setting_id):
    """설정 삭제 처리"""
    try:
        if config_manager.delete_setting(setting_id):
            flash('설정이 삭제되었습니다.', 'success')
        else:
            flash('삭제할 설정을 찾지 못했습니다.', 'error')
    except Exception as e:
        flash(f'삭제 중 오류가 발생했습니다: {str(e)}', 'error')
    return redirect(url_for('settings_list_page'))

@app.route('/schemas')
def schemas_page():
    """스키마 관리 페이지"""
    return render_template('schemas.html', schema_files=get_schema_files())

@app.route('/schemas/upload', methods=['POST'])
def upload_schema_action():
    """스키마 파일 업로드 처리"""
    if 'schema_file' not in request.files:
        flash('파일 부분이 없습니다.', 'error')
        return redirect(url_for('schemas_page'))
    
    file = request.files['schema_file']
    if file.filename == '':
        flash('선택된 파일이 없습니다.', 'error')
        return redirect(url_for('schemas_page'))

    if file and file.filename.endswith('.csv'):
        # 한글 등 유니코드 파일명을 그대로 사용 (secure_filename은 한글을 제거함)
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash(f"'{filename}' 파일이 성공적으로 업로드되었습니다.", 'success')
    else:
        flash('CSV 파일만 업로드할 수 있습니다.', 'error')
        
    return redirect(url_for('schemas_page'))

@app.route('/schemas/delete/<path:filename>', methods=['POST'])
def delete_schema_action(filename):
    """스키마 파일 삭제 처리"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            flash(f"'{filename}' 파일이 삭제되었습니다.", 'success')
        else:
            flash('삭제할 파일을 찾지 못했습니다.', 'error')
    except Exception as e:
        flash(f'파일 삭제 중 오류가 발생했습니다: {str(e)}', 'error')
        
    return redirect(url_for('schemas_page'))

@app.route('/intro')
def intro_page():
    """소개 페이지 (README.md를 가이드로 보여줌)"""
    with open('README.md', encoding='utf-8') as f:
        readme_md = f.read()
    readme_html = markdown.markdown(readme_md, extensions=['fenced_code', 'tables'])
    return render_template('intro.html', readme_html=readme_html)

# --- API for Frontend ---

@app.route('/api/settings/<int:setting_id>')
def get_setting_details_api(setting_id):
    """설정 ID에 해당하는 설정 상세 정보를 JSON으로 반환합니다."""
    setting = config_manager.get_setting_by_id(setting_id)
    if setting:
        return jsonify(setting.to_dict())
    return jsonify({'error': 'Setting not found'}), 404

@app.route('/api/settings/<int:setting_id>', methods=['PATCH'])
def update_setting_api(setting_id):
    data = request.json
    setting = config_manager.update_setting(setting_id, data)
    if setting:
        return jsonify({'success': True, 'setting': setting.to_dict()})
    return jsonify({'success': False, 'error': '설정 수정 실패'}), 400

@app.route('/api/settings', methods=['POST'])
def add_setting_api():
    data = request.json
    setting = config_manager.add_setting(data)
    if setting:
        return jsonify({'success': True, 'setting': setting.to_dict()})
    return jsonify({'success': False, 'error': '설정 추가 실패'}), 400

# --- BQ Job API Routes ---

def _run_job(job_function, config, success_message):
    """BQ 작업을 실행하고 결과를 JSON으로 반환하는 래퍼 함수"""
    if not config:
        return jsonify({
            'success': False,
            'message': '유효한 설정을 찾을 수 없습니다. 먼저 설정을 선택해주세요.'
        })
    try:
        details = job_function(config.to_dict())
        details['message'] = success_message
        return jsonify({'success': True, 'details': details})
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'작업 중 오류 발생: {str(e)}',
            'error_details': traceback.format_exc()
        })

@app.route('/run_job/<string:job_name>/<int:setting_id>', methods=['POST'])
def run_job_route(job_name, setting_id):
    """지정된 ID의 설정으로 BQ 작업을 실행합니다."""
    config = config_manager.get_setting_by_id(setting_id)
    
    if job_name == 'create_table':
        return _run_job(
            bq_manager.create_bq_table, 
            config, 
            f"✅ 테이블 생성 완료: {config.bq_table_id}"
        )
    elif job_name == 'append_data':
        return _run_job(
            bq_manager.append_to_bq, 
            config, 
            "✅ 데이터 추가 완료"
        )
    elif job_name == 'update_data':
        return _run_job(
            bq_manager.update_bq_table, 
            config, 
            "✅ 데이터 덮어쓰기 완료"
        )
    else:
        return jsonify({'success': False, 'message': '알 수 없는 작업입니다.'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050) 