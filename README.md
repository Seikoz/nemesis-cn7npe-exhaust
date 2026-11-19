# CN7NPE 배기 플랩 제어 연구

**현재 v0.1.0은 분석 파일 수집 도구입니다. 플랩 열림·닫힘·순정 자동 제어는 구현되지 않았습니다.**
제어 명령과 실차 동작이 확인되지 않아 제어 기능을 제공하는 릴리스는 아직 만들 수 없습니다.

목표는 한국형 아반떼 N 페이스리프트의 배기 플랩을 **열림 / 닫힘 / 순정 자동 복귀**로 제어하는 NEMESIS 패키지입니다. 순정 N Custom의 배기음 단계 변경을 플랩 강제 개폐라고 표시하지 않습니다.

## 현재 다운로드

[분석용 USB ZIP v0.1.0](https://github.com/Seikoz/nemesis-cn7npe-exhaust/releases/tag/v0.1.0-research)

| 항목 | 현재 상태 |
| --- | --- |
| 대상 소프트웨어 | `CN7NPE.KOR.0000.V039.001.260902` 또는 `CN7NPE.KOR.S5W_M.V039.001.260902` |
| 대상 하드웨어 | TCC803x, NEMESIS가 이미 정상 실행되는 Gen5W |
| 분석 자료 추출 | USB에서 한 번 실행, 선택한 순정 파일을 USB에 복사 |
| 플랩 제어 API·값·자동 복귀 | 미확인 / 미구현 |
| 실차 검증 | 미실시 |

## USB에서 분석 자료 만들기

1. 릴리스의 `NEMESIS-CN7NPE-Exhaust-Research-v0.1.0-USB.zip`을 내려받습니다. GitHub가 자동으로 제공하는 Source code ZIP과 다릅니다.
2. ZIP 안의 `NEMESIS.data`, `collect.sh`, `CN7NPE-EXHAUST-RESEARCH.txt`, `INSTALL-KO.md`를 USB 최상위에 풉니다. 기존 USB의 `NEMESIS.data`와 겹치므로 별도 USB를 사용하거나 기존 파일을 PC에 먼저 보관하세요. 포맷할 필요는 없습니다.
3. 주차 상태에서 내비가 부팅된 뒤 데이터 USB 포트에 연결하고 NEMESIS의 스크립트 실행 질문에 동의합니다. 이 도구는 설치되는 앱이 아니며 My Packages에 추가되지 않습니다.
4. 완료 메시지까지 USB를 빼지 마세요. 추출 후 USB의 `CN7NPE-exhaust-private-1/report.txt`를 확인합니다. 두 번째 실행은 `-2`처럼 새 폴더를 만들며 최대 20개까지 보관합니다.
5. `collection=COMPLETE`는 **파일 추출 완료**를 뜻합니다. `INCOMPLETE`나 실패 메시지가 보이면 생성된 폴더를 그대로 보관하세요.
6. PC에서 그 폴더를 ZIP으로 압축해 개발 대화에 **비공개로** 첨부해 주세요. **제조사 파일이므로 공개 GitHub 이슈·저장소·릴리스에 올리지 마세요.** 공개 코드와 릴리스에는 이 파일을 포함하지 않습니다.

완료 후 USB의 수집 도구와 결과 폴더를 삭제하면 됩니다. 헤드유닛에서 제거할 패키지나 자동 시작 서비스는 없습니다.

## 무엇을 읽고 쓰는가

- 읽기: 제품·플랫폼·Android 버전의 지정된 속성 네 개, 시스템 패키지의 N 모드 앱 경로, `/system/framework/`의 automotive 및 분석에 필요한 지정 JAR/ODEX, N 모드 APK/ODEX.
- 쓰기: USB에 새로 만든 `CN7NPE-exhaust-private-N/` 폴더만 사용합니다. 폴더를 만들 수 없으면 중단하며 기존 결과를 덮어쓰지 않습니다.
- 수집 범위에 `/data`, 연락처, VIN, 모뎀, 통화기록, 로그 버퍼, 설정 DB, 전체 속성 덤프는 포함하지 않습니다. 추출된 순정 바이너리 자체에 제조사 문자열·식별자가 있을 수 있으므로 결과 전체를 비공개로 다룹니다.
- ECU/MICOM/CAN 송신, Binder 제어 호출, 플랩 조작, 시스템 파일 변경, 재부팅은 수행하지 않습니다.

## 제어판을 만들기 위해 남은 일

정확한 펌웨어의 N 모드 앱과 `automotive` 구현에서 플랩 직접 제어 또는 순정 배기 설정 경로를 찾습니다. **직접 제어가 제공되지 않을 가능성도 있으며, 파일 추출이 제어 가능성을 보장하지는 않습니다.** 호출 인자와 응답, 실제 플랩 상태 확인, 순정 자동 제어로 돌리는 방법을 확인한 뒤 제어판을 구현합니다. 순정 자동 복귀가 검증되지 않으면 제어 ZIP을 게시하지 않습니다. 실제 동작과 재시작·제거 시 복귀는 해당 차량에서 별도로 검증해야 합니다.

## 개발과 검증

Python 3.10 이상으로 `python build.py`를 실행하면 `dist/`에 USB ZIP과 `SHA256SUMS.txt`를 만듭니다. ZIP은 고정된 파일 목록으로 만들며 제조사 바이너리나 수집 결과를 포함하지 않습니다.

`python -m unittest discover -s tests -v`는 모의 헤드유닛에서 버전 거부, 추출 완료·누락·실패, 기존 결과 보존을 검증합니다. 셸 테스트에는 POSIX `sh`가 필요하며 Windows에서는 `TEST_SH`에 Git for Windows의 `sh.exe` 경로를 지정합니다. PC 테스트는 차량의 제어 가능성이나 실차 동작을 입증하지 않습니다.

## 근거

- [NEMESIS의 USB 스크립트 실행 규격](https://github.com/xwtk/hmg_nemesis/blob/main/06-Run-Scripts.md)
- [NEMESIS 패키지 규격](https://github.com/xwtk/hmg_nemesis/blob/main/05-Packages.md)
- [HMG-API 차량 명령 목록](https://github.com/Open-HMG/HMG-API/blob/5a642c5b47b5d9fc5e967603d764c39ba0b77dfd/docs/vehicle-commands.md): 확인 시점에 배기 플랩 명령은 없음.
- [HMG-API의 MICOM 인터페이스 설명](https://github.com/Open-HMG/HMG-API/blob/5a642c5b47b5d9fc5e967603d764c39ba0b77dfd/docs/micom-map.md): 내비 Android가 차량 CAN을 직접 보는 구조로 가정할 수 없음.

## License

이 저장소의 자체 작성 코드·문서는 MIT License입니다. NEMESIS나 HMG-API 코드를 복사하거나 배포하지 않습니다. 수집된 제조사 바이너리에는 이 라이선스가 적용되지 않습니다. 현대자동차 및 NEMESIS 공식 프로젝트와 무관한 커뮤니티 연구입니다.
