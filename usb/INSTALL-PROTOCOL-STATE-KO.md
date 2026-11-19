# 저장된 진단 프로토콜 확인 v0.3.2-local

HCAN 코드에서 확인한 **ECU별 KWP/UDS 선택 캐시**만 확인하는 연구 도구입니다. 배기 플랩 제어 기능은 없습니다. 버전 이름 `0.3.2-local`은 기존 로컬 배포와 구분 없이 유지합니다.

## 목적과 읽는 범위

기존 추출은 순정 코드였으며, 코드에는 KWP와 UDS 경로가 모두 있습니다. 이번에는 순정 진단 서비스가 저장한 선택값을 확인합니다. 코드에서 이 파일의 자료형은 ECU 32개에 대한 UNKNOWN/KWP/UDS 바이트 배열 하나입니다. EMS 항목은 인덱스 4, 별도 CS EMS 항목은 인덱스 30입니다.

고정 경로 두 곳만 확인합니다. 저장소 사양에 따라 사용하는 루트가 달라 두 경로를 모두 확인하며, 둘 다 있으면 어느 쪽이 현재 활성 파일인지 단정하지 않습니다.

- `/data/misc/infobank/diagInfo/DiagProtocalType.dat`
- `/securedata/misc/infobank/diagInfo/DiagProtocalType.dat`

이름의 `Protocal` 철자는 순정 코드 그대로입니다. 파일당 4KiB, 복사 합계 8KiB 제한이며 경로 중 심볼릭 링크가 있으면 따라가지 않습니다. 다른 `/data` 파일·진단 결과 DB·VIN·연락처·로그는 수집하지 않습니다. 기존 APK/JAR/ODEX도 다시 복사하지 않습니다.

파일이 없어도 진단을 시작해 만들지 않습니다. **캐시 값은 과거 저장된 선택이며 현재 ECU와 통신했다는 증거나 AEV 구동 가능 판정이 아닙니다.**

## 실행

1. 기존 USB의 `NEMESIS.data`를 먼저 PC에 보관하거나 별도 USB를 사용합니다. 이 ZIP의 모든 파일을 USB 최상위에 풉니다.
2. 주차 상태에서 내비 부팅 후 데이터 USB 포트에 연결하고 NEMESIS 스크립트 실행에 동의합니다. 지원 대상은 기존 한국 CN7N PE V039.001.260902/TCC803x 환경입니다.
3. 퍼센트·현재 파일을 확인하고 **100% 이후 NEMESIS 완료 알림까지** 기다린 뒤 USB를 분리합니다. 크기 확인 15초, 복사 60초, 저장 마무리 60초 제한이며 파일이 없으면 복사하지 않습니다.
4. 새 `CN7NPE-exhaust-private-N` 폴더를 PC 프로젝트의 `private/protocol-state` 아래로 복사합니다. 기존 결과와 섞거나 덮어쓰지 마세요.

`collection=COMPLETE`는 두 경로 확인과 USB 저장 완료를 뜻합니다. 파일이 없어도 확인 작업은 완료될 수 있습니다. `report.txt`에서 다음을 구분합니다.

- `protocol_state=AVAILABLE_FOR_OFFLINE_DECODE`: 캐시를 복사했습니다. PC 해석이 필요합니다.
- `protocol_state=UNAVAILABLE`: 파일 없음·빈 파일·심볼릭 링크·크기 제한 등으로 복사하지 않았습니다. 보고서에 이유가 남습니다. UDS/KWP 여부는 미확인입니다.

## PC에서 해석

ZIP의 `pc/decode_protocol_state.py`는 Python 3 표준 라이브러리만 사용합니다. Java 객체를 역직렬화하거나 실행하지 않고, 확인된 클래스·필드·32바이트 배열의 정확한 형태만 읽습니다. 다른 형태나 값이면 추정하지 않고 거부합니다.

```text
python pc/decode_protocol_state.py 결과폴더/state/data_diagInfo_DiagProtocalType.dat
```

`ems_saved_protocol`이 `UDS`라면 기본 EMS 슬롯에 저장된 선택값이 UDS라는 뜻입니다. 프로비저닝에 따라 EMS가 다른 논리 슬롯을 사용할 수 있어 이 값만으로 현재 활성 경로를 확정하지 않습니다. `UNKNOWN`이면 저장된 선택이 미상입니다. `AEV_control`은 항상 `UNVERIFIED`, `ECU_exchange`는 항상 `NOT_TESTED`로 표시합니다. 파일이 두 개이면 각각 해석하고 차이를 보관합니다.

이 도구는 ECU/MICOM 요청, Binder 차량 제어 호출, 소켓 접속, 진단 세션 변경, 시스템 설정·캐시 수정, 재부팅을 하지 않습니다. 쓰기는 USB의 새 결과 폴더에 한정됩니다. 실제 차량에서 이 버전의 수집은 아직 검증하지 않았습니다. 추출 결과는 비공개로 보관하세요.
