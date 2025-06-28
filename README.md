# BigQuery 관리 도구

Google Sheets에서 BigQuery로 데이터를 관리하는 웹 기반 도구입니다.

## 🚀 기능

- **테이블 생성**: 스키마 정의를 기반으로 BigQuery 테이블 생성
- **데이터 추가**: Google Sheets에서 BigQuery로 데이터 추가 (Append)
- **데이터 덮어쓰기**: Google Sheets에서 BigQuery로 데이터 전체 교체
- **설정 아카이빙**: 자주 사용하는 설정을 이름과 함께 저장하고 불러오는 기능 (CRUD)
- **모바일 퍼스트 UI**: 모바일과 데스크톱에서 모두 사용 가능한 반응형 웹 인터페이스
- **실시간 결과 표시**: 작업 진행 상황과 결과를 실시간으로 확인

## 📋 요구사항

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) 0.7.16 이상 (초고속 패키지/가상환경 관리)
- Google Cloud Service Account 키 파일 (`credentials.json`)
- Google Sheets API 접근 권한
- BigQuery API 접근 권한

## 🛠️ 설치 및 실행 (uv 기반)

### 1. uv 설치 (Homebrew 예시)
```bash
brew install astral-sh/uv/uv
```

### 2. 가상환경 생성 및 의존성 설치
```bash
uv venv
uv pip install -r pyproject.toml
```

또는 아래처럼 한 번에 패키지 설치도 가능합니다:
```bash
uv add
```
(이미 pyproject.toml에 dependencies가 정의되어 있으면 위 명령은 생략 가능)

### 3. 애플리케이션 실행
```bash
uv run python app.py
```

※ 별도의 가상환경 진입(source .venv/bin/activate) 없이 uv 명령어만으로 실행하면 됩니다.

### 4. 웹 브라우저에서 접속
```
http://localhost:5050
```

## 📝 사용법

### 1. 설정 구성
- **Google Sheets ID**: Google Sheets URL에서 추출한 ID
- **헤더 범위**: 헤더가 있는 셀 범위 (예: `시트명!A1:CD1`)
- **데이터 범위**: 데이터가 있는 셀 범위 (예: `시트명!A2000:CD4000`)
- **BigQuery 테이블 ID**: `project.dataset.table_name` 형식
- **스키마 CSV 파일**: 컬럼 정의가 있는 CSV 파일명

### 2. 작업 실행
1.  **현재 설정 임시저장**: 입력한 설정을 현재 세션에 임시로 저장합니다.
2.  **설정 아카이브 (선택 사항)**: 자주 쓰는 설정은 '아카이브 이름'을 지정하여 영구 저장할 수 있습니다.
3.  **작업 버튼 클릭**: '테이블 생성', '데이터 추가' 등의 작업을 실행합니다.


## ⚠️ 주의사항

- `credentials.json` 파일은 프로젝트 루트에 위치해야 합니다
- Google Cloud Service Account에 적절한 권한이 부여되어야 합니다
- BigQuery 테이블 ID는 올바른 형식이어야 합니다
- 스키마 CSV 파일의 컬럼 순서가 Google Sheets와 일치해야 합니다

## 🐛 문제 해결

### 인증 오류
- `credentials.json` 파일이 올바른 위치에 있는지 확인
- Google Cloud Service Account 권한 확인

### 컬럼 불일치 오류
- 스키마 CSV 파일의 컬럼 순서와 Google Sheets의 컬럼 순서가 일치하는지 확인
- 컬럼명에 공백이나 특수문자가 없는지 확인

### 데이터 타입 오류
- 스키마 CSV 파일의 데이터 타입이 BigQuery에서 지원하는 타입인지 확인
- 데이터 변환 중 오류가 발생하는 경우 원본 데이터 형식 확인 