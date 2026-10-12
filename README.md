# InBody OpenDART Financial Agent & Dashboard

[![🔗 대시보드 바로가기](https://img.shields.io/badge/%F0%9F%94%97_%EB%8C%80%EC%8B%9C%EB%B3%B4%EB%93%9C_%EB%B0%94%EB%A1%9C%EA%B0%80%EA%B8%B0-0D6EFD?style=for-the-badge)](https://hsc-class02.github.io/AK_InBody/)

인바디(041830)의 OpenDART 정기보고서에서 재무제표를 수집하고, 주요 재무비율을 계산해 GitHub Pages 대시보드로 배포하는 프로젝트입니다.

## Dashboard and data pipeline

- **Dashboard:** https://hsc-class02.github.io/AK_InBody/
- **Source data:** DART API 원문 응답을 `data/raw/`에 JSON으로 저장
- **Processed data:** 연간·반기·분기 정규화 결과는 `data/processed/financials.csv`, 수집 범위는 `data/processed/coverage.json`
- **Reports:** 사업보고서(11011), 반기보고서(11012), 1분기보고서(11013), 3분기보고서(11014)
- **Refresh:** 매월 1일 오전 9시 17분(KST, UTC 00:17)에 실행. Actions에서 수동 실행도 가능
- **Deployment:** 수집 후 대시보드 HTML이 갱신되면 GitHub Pages 배포 워크플로가 실행됩니다.

## Initial setup / secrets

1. OpenDART에서 발급받은 40자리 API 키를 등록합니다.
2. GitHub 저장소의 **Settings → Secrets and variables → Actions → New repository secret**으로 이동합니다.
3. Secret 이름을 정확히 `DART_API_KEY`로 입력하고 Value에는 API 키만 넣습니다. 키를 코드, README, CSV 또는 커밋 메시지에 넣지 마세요.
4. **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 설정합니다.
5. **Actions → Monthly DART Update → Run workflow**를 눌러 첫 수집을 실행합니다. 실행 로그에서 인증·쿼터 오류와 수집 건수를 확인하세요.

실제 워크플로 파일은 반드시 `.github/workflows/` 안에 있어야 합니다. 다운로드 패키지의 일반 `workflows/` 폴더는 숨김 경로를 포함하지 않게 하기 위한 설치용 복사본입니다. 다른 저장소에 설치할 때는 YAML 파일 두 개를 `.github/workflows/`로 옮기세요.

## Historical coverage limitation

`config.json`의 `start_year`는 2010으로 설정되어 있습니다. 다만 OpenDART의 [단일회사 전체 재무제표 API 안내](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020)는 **2015년 이후 데이터 제공**으로 명시합니다. 따라서 표준 API만으로 2010–2014년 수치를 확보했다고 주장하지 않습니다. 이 구간의 원문 공시/XBRL을 수집하려면 별도의 과거 공시 파서가 필요하며, 현재 파이프라인은 해당 연도를 커버리지 메타데이터에 명시합니다.

## Financial metrics and methodology

주요 금액은 매출액, 매출원가, 매출총이익, 판매비와관리비, 영업이익, 세전이익, 당기순이익, 자산·부채·자본, 현금, 매출채권, 재고자산, 유형자산, 이자부차입금(계정이 식별되는 경우), 영업·투자·재무 현금흐름, CAPEX 및 FCF입니다.

주요 비율은 매출증가율, 매출총이익률, 영업이익률, 순이익률, EBITDA 마진(상각비 계정이 확인되는 경우), ROA, ROE, ROIC(유효세율 및 투하자본을 산출할 수 있는 경우), 유동비율, 당좌비율, 부채비율(총부채/자본), 자기자본비율, 차입금의존도, 이자보상배율, 순차입금/EBITDA, 총자산회전율, 매출채권회전율/DSO, 재고자산회전율/DIO, CFO/순이익 등을 포함합니다.

- 연결재무제표(CFS)를 우선 사용하고, 없을 때 별도재무제표(OFS)를 사용합니다. 표의 **FS** 열을 확인하여 서로 다른 기준을 무심코 비교하지 마세요.
- OpenDART는 반기·분기 손익계산서에 3개월 금액(`thstrm_amount`)과 누적 금액(`thstrm_add_amount`)을 구분합니다. 파이프라인은 누적 흐름에서 Q1–Q4의 독립 분기 금액을 계산하고, 분기 말 재무상태표는 각 보고서 시점의 잔액을 사용합니다.
- ROA/ROE는 평균 잔액을 분모로 사용합니다. 연간은 연간 수치이며, 반기·분기 비율은 해당 기간 실적 기준으로 계산하고 연율화하지 않습니다.
- 비용·현금유출 계정은 계정명이 정확히 매핑될 때에만 계산합니다. EBITDA·ROIC·FCF는 필수 항목이 누락되면 빈 값으로 남기며, 임의의 값으로 채우지 않습니다.
- 매입액을 표준계정으로 일관되게 확보하기 어려우므로 DPO 및 CCC는 계산하지 않습니다. PER/PBR/EV-EBITDA/FCF 수익률은 시장가격, 발행주식 수 및 기업가치 자료가 필요하므로 재무제표만으로 추정하지 않습니다.
- 금액은 대시보드 표에서 **억원(₩100m)** 단위로 표시됩니다. 원자료 CSV는 OpenDART의 원 단위를 보존합니다.

## Domestic peer firms

| 기업 | 종목코드 | 비교 구분 | 비교 시 유의사항 |
|---|---:|---|---|
| 셀바스헬스케어 | 208370 | 가장 가까운 국내 비교군 | 체성분분석기와 병원용 의료기기 사업. 인바디와 규모·제품구성은 다를 수 있음. [공식 소개](https://www.selvashealthcare.com/kr/company/) |
| 아이센스 | 099190 | 인접 의료기기 | 혈당 측정·진단기기 중심으로 체성분 분석기 직접 경쟁사는 아님 |
| 비트컴퓨터 | 032850 | 인접 디지털 헬스케어 | 의료정보·디지털 헬스케어 중심으로 하드웨어 제품구성이 다름 |

피어 그룹은 직접 제품 중첩과 인접 산업 회사를 구분하기 위한 참고 목록입니다. 투자 판단 시 최신 사업보고서 및 사업 부문별 매출을 별도로 확인해야 합니다.

## Dashboard shortcut in About

README 상단 배지는 자동으로 대시보드에 연결됩니다. 저장소 오른쪽 **About → ⚙️ → Website**에는 `https://hsc-class02.github.io/AK_InBody/`를 입력하세요. GitHub 저장소의 About 메타데이터는 일반 파일 커밋만으로 변경되지 않으므로 이 단계는 저장소 설정 화면에서 확인해야 합니다.

## Operations and troubleshooting

- 실제 자동 수집 워크플로는 `.github/workflows/monthly-update.yml`, Pages 배포 워크플로는 `.github/workflows/pages.yml`입니다. 루트의 이전 `workflows/` 사본은 GitHub Actions가 실행하는 위치가 아닙니다.
- API 키가 없거나 잘못되었거나 쿼터 초과가 발생하면 데이터 수집 단계를 실패 처리하여 빈 결과를 조용히 성공으로 위장하지 않습니다.
- 수집 실패 및 미접수 기간은 `coverage.json`에 기록됩니다. 보고서가 아직 제출되지 않은 최신 연도의 기간은 빈 값일 수 있습니다.
- GitHub Actions 실행 결과가 성공이어도, 첫 실행 후 **Pages URL**, Actions job 로그, `financials.csv`의 기간/FS 기준을 함께 확인하세요.
- GitHub Pages 예약 실행은 GitHub 부하에 따라 예약 시각보다 늦어질 수 있습니다.

Source: [OpenDART single-company full financial statements API](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020).
