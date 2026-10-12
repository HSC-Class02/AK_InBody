# InBody OpenDART Financial Agent & Dashboard

[![🔗 대시보드 바로가기](https://img.shields.io/badge/%F0%9F%94%97_%EB%8C%80%EC%8B%9C%EB%B3%B4%EB%93%9C_%EB%B0%94%EB%A1%9C%EA%B0%80%EA%B8%B0-0D6EFD?style=for-the-badge)](https://hsc-class02.github.io/AK_InBody/)

OpenDART에서 InBody(041830)의 정기보고서 재무 데이터를 수집하고, 재무비율을 계산하여 GitHub Pages 대시보드로 배포하는 프로젝트입니다.

## 핵심 기능
- 사업보고서(11011), 반기보고서(11012), 1분기(11013), 3분기(11014) 수집
- 2010년부터 루프를 돌되, **표준 재무제표 OpenDART API는 공식 가이드상 일반적으로 2015년부터 제공**되므로 2010~2014는 자동으로 비어 있을 수 있습니다. 해당 기간을 완전 수집하려면 원문 공시/XBRL fallback을 추가해야 합니다.
- Annual / Half-year / Quarterly 표 분리
- 매출, 매출총이익, 영업이익, 순이익, 자산·부채·자본, 현금, 채권, 재고, 유형자산, CFO/CFI/CFF 및 가이드 기반 비율 계산
- 매월 1일 09:17 KST 자동 갱신

## 설치
1. OpenDART에서 API 키 발급
2. GitHub 저장소 → Settings → Secrets and variables → Actions → New repository secret
3. Name: `DART_API_KEY`, Value: 발급받은 40자리 키
4. ZIP 안의 `workflows/monthly-update.yml` 및 `workflows/pages.yml`을 GitHub 웹사이트에서 **각각 `.github/workflows/` 경로로 생성**하세요. ZIP에는 숨김 파일/폴더가 없습니다. 기존에 같은 경로의 워크플로가 있으면 중복 생성하지 말고 교체하세요.
5. Settings → Pages → Source를 **GitHub Actions**로 설정합니다.
6. Actions에서 `Monthly DART Update`를 한 번 수동 실행합니다.

## About 링크
Repository 우측 **About → ⚙️ → Website**에 아래 주소를 입력하세요.
`https://hsc-class02.github.io/AK_InBody/`
GitHub의 About 설정은 저장소 메타데이터이므로 파일 업로드만으로 자동 변경되지 않습니다.

## 재무비율 원칙
첨부 가이드의 정의를 따라 금액과 비율을 함께 표시하고, 연결/별도와 기간을 섞지 않으며 ROA·ROE는 가능한 경우 평균 잔액을 사용합니다. FCF는 `CFO - 현금 기준 CAPEX`, 순차입금은 `이자부차입금 - 현금및현금성자산`이지만, 계정 매핑이 불확실하면 임의 추정하지 않습니다.

## 국내 비교기업

| 기업 | 종목코드 | 비교 범위 및 한계 |
|---|---|---|
| 셀바스헬스케어 | 208370 | 체성분분석 및 의료기기 사업에서 제품 일부 중첩; 기업 규모·사업구성 상이 |
| 비트컴퓨터 | 032850 | 디지털 헬스케어 인접 비교군; 체성분 분석기 직접 경쟁사는 아님 |
| 아이센스 | 099190 | 진단·측정 의료기기 인접 비교군; 혈당 측정 중심으로 직접 경쟁사는 아님 |



### Workflow 경로 수정 (2026-10)
GitHub Actions 워크플로는 반드시 `.github/workflows/monthly-update.yml` 및 `.github/workflows/pages.yml`에 위치해야 합니다. 예전 루트 `workflows/` 폴더는 사용하지 않습니다. GitHub Settings → Actions → General에서 Actions 허용 및 Workflow permissions Read and write permissions를 확인하세요. Pages Source는 GitHub Actions로 선택하세요.


## 검증 및 주의사항
- 워크플로 YAML 구문과 Python 소스 컴파일을 로컬 검사했습니다. 실제 GitHub Actions 성공과 DART API 응답은 GitHub에서 실행해야 확인할 수 있습니다.
- `main`이 아닌 기본 브랜치를 사용한다면 `workflows/pages.yml`의 branches 값을 변경하세요.
- 수집에 실패한 연도/기간은 건너뛰므로 2010~2014년의 완전 수집을 보장하지 않습니다.
- 분기 표의 Q1/Q3 수치는 독립 3개월 실적이 아니라 누적기간(YTD)입니다. 반기 역시 누적 6개월 실적입니다.
- 연결재무제표가 없을 때 별도재무제표로 대체하므로 비교 전 `fs_div`를 확인하세요.
- 첫 수동 실행 뒤 Actions 로그와 GitHub Pages URL을 확인하세요.
