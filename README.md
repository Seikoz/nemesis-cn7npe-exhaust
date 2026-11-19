# CN7NPE 배기 플랩 제어 연구

**현재 v0.2.1은 차량 서비스 구현 파일을 보완 추출하는 분석 도구입니다. 플랩 열림·닫힘·순정 자동 제어는 구현되지 않았습니다.**
제어 명령과 실차 동작이 확인되지 않아 제어 기능을 제공하는 릴리스는 아직 만들 수 없습니다.

목표는 한국형 아반떼 N 페이스리프트의 배기 플랩을 **열림 / 닫힘 / 순정 자동 복귀**로 제어하는 NEMESIS 패키지입니다. 순정 N Custom의 배기음 단계 변경을 플랩 강제 개폐라고 표시하지 않습니다.

## 현재 다운로드

[차량 서비스 보완 추출 USB ZIP v0.2.1](https://github.com/Seikoz/nemesis-cn7npe-exhaust/releases/tag/v0.2.1-research)

기존에 N 모드 앱·기본 프레임워크를 추출한 분은 **보완 추출 ZIP**을 사용하세요. 이 ZIP은 `automotive-service.jar`/`.odex`와 파일 이름 목록만 추가로 수집하며, 50MB N 모드 앱을 다시 복사하지 않습니다. [보완 추출 사용법](usb/INSTALL-SERVICES-KO.md)

추출 자료가 이 PC의 `private/`에 있으면 첨부 용량 제한과 관계없이 로컬 분석이 가능합니다. 제조사 파일과 분석 파생물은 Git에서 제외합니다. 최초 전체 수집 절차는 아래의 v0.2.0 설명을 참고하되, 0.2.0의 마지막 단계에서 실패한 경우 결과 폴더를 보관하세요.

| 항목 | 현재 상태 |
| --- | --- |
| 대상 소프트웨어 | `CN7NPE.KOR.0000.V039.001.260902` 또는 `CN7NPE.KOR.S5W_M.V039.001.260902` |
| 대상 하드웨어 | TCC803x, NEMESIS 1.16.7 이상이 이미 정상 실행되는 Gen5W |
| 분석 자료 추출 | USB에서 한 번 실행, 선택한 순정 파일을 USB에 복사 |
| 플랩 제어 API·값·자동 복귀 | 미확인 / 미구현 |
| 실차 검증 | 미실시 |

## USB에서 분석 자료 만들기

1. 릴리스의 `NEMESIS-CN7NPE-Exhaust-Research-v0.2.0-USB.zip`을 내려받습니다. GitHub가 자동으로 제공하는 Source code ZIP과 다릅니다.
2. ZIP 안의 파일 전체를 USB 최상위에 풉니다. `progress.sh`도 반드시 필요합니다. 기존 USB의 `NEMESIS.data`와 겹치므로 별도 USB를 사용하거나 기존 파일을 PC에 먼저 보관하세요. 포맷할 필요는 없습니다.
3. 주차 상태에서 내비가 부팅된 뒤 데이터 USB 포트에 연결하고 NEMESIS의 스크립트 실행 질문에 동의합니다. 이 도구는 설치되는 앱이 아니며 My Packages에 추가되지 않습니다.
4. 화면에 퍼센트·단계·현재 파일·복사/없음 개수가 표시됩니다. **100%가 나온 다음 NEMESIS의 완료 알림까지 확인하고** USB를 분리하세요. 추출 후 USB의 `CN7NPE-exhaust-private-1/report.txt`를 확인합니다. 두 번째 실행은 `-2`처럼 새 폴더를 만들며 최대 20개까지 보관합니다.
5. `collection=COMPLETE`는 **파일 추출 완료**를 뜻합니다. `INCOMPLETE`나 실패 메시지가 보이면 생성된 폴더를 그대로 보관하세요.
6. PC에서 그 폴더를 ZIP으로 압축해 개발 대화에 **비공개로** 첨부해 주세요. **제조사 파일이므로 공개 GitHub 이슈·저장소·릴리스에 올리지 마세요.** 공개 코드와 릴리스에는 이 파일을 포함하지 않습니다.

완료 후 USB의 수집 도구와 결과 폴더를 삭제하면 됩니다. 헤드유닛에서 제거할 패키지나 자동 시작 서비스는 없습니다.

## 진행률과 오류 표시

화면은 NEMESIS의 기존 진행 팝업을 사용합니다. 별도 앱을 설치하지 않습니다. 화면의 막대는 10칸 문자 막대입니다.

```text
분석 파일 추출 v0.2.0 · 40%
[####------] 작업 단계 기준
2/5 프레임워크 수집
현재: services.odex · 복사 제한 60초
복사 4 / 없음 3
완료 알림 전에는 USB를 빼지 마세요.
```

- **진행률은 완료한 작업 단계 기준이며, 바이트 전송률·경과 시간·예상 남은 시간이 아닙니다.** 대상 확인 → 프레임워크 수집 → N 모드 앱 확인 → 앱 수집 → 결과 확인과 USB 저장 마무리 순서입니다. 파일 하나를 처리하는 동안 퍼센트가 그대로일 수 있습니다.
- `없음`에는 이 펌웨어가 사용하지 않는 선택 파일도 포함됩니다. 필수 automotive 파일이나 N 모드 APK가 없으면 완료 처리하지 않습니다.
- 앱 목록/경로 확인은 30초, 파일 복사와 저장 마무리는 각각 60초, 화면 갱신 호출은 5초 제한을 적용합니다. 명령 실패·시간 초과·진행 화면 오류는 추출을 중단하며 100% 화면을 표시하지 않습니다. 커널 수준의 USB 입출력 정지는 종료가 더 늦어질 수 있습니다.
- 정상 흐름에서 100%는 필수 파일 확인과 `sync` 성공 뒤에 표시됩니다. 이어 NEMESIS가 `Operation completed successfully.`를 표시합니다. 실패한 작업은 `Operation failed.`로 끝날 수 있습니다.
- 중간 상태는 결과 폴더의 `progress.txt`, 단계 기록은 `events.log`, 화면 호출 기록은 `ui.log`에 남습니다. 오류 화면이 보이면 성공으로 간주하지 말고 결과 폴더를 보관해 주세요. USB 오류로 기록 자체가 실패하면 마지막 상태가 남지 않을 수 있습니다.
- 공개된 NEMESIS 진행 팝업 구현을 기준으로 모의 검증했습니다. 실제 해당 헤드유닛에서의 화면 가독성과 동작은 아직 확인되지 않았습니다.

## 무엇을 읽고 쓰는가

- 읽기: 제품·플랫폼·Android 버전의 지정된 속성 네 개, 시스템 패키지의 N 모드 앱 경로, `/system/framework/`의 automotive 및 분석에 필요한 지정 JAR/ODEX, N 모드 APK/ODEX.
- 쓰기: USB에 새로 만든 `CN7NPE-exhaust-private-N/` 폴더만 사용합니다. 폴더를 만들 수 없으면 중단하며 기존 결과를 덮어쓰지 않습니다.
- 수집 범위에 `/data`, 연락처, VIN, 모뎀, 통화기록, 로그 버퍼, 설정 DB, 전체 속성 덤프는 포함하지 않습니다. 추출된 순정 바이너리 자체에 제조사 문자열·식별자가 있을 수 있으므로 결과 전체를 비공개로 다룹니다.
- ECU/MICOM/CAN 송신, 차량 제어 호출, 플랩 조작, 시스템 파일 변경, 재부팅은 수행하지 않습니다. 화면 표시에만 Android ActivityManager를 사용합니다.

## 제어판을 만들기 위해 남은 일

v0.2.1 보완 추출이 실차에서 정상 완료됐고, 차량 서비스 구현까지 분석했습니다. 확인된 경로는 N 모드 앱 → `NModeManager` → `ISystemService` → `SystemService` → MICOM 전송 경로입니다. 순정 단계 Normal / Sport / Sport+는 강제 열림·닫힘·자동 복귀로 검증되지 않았습니다. `resetIndividualDriveModeInstance()`는 내비 캐시 초기화일 뿐, 차량으로 제어 해제 명령을 보내지 않습니다. [분석 근거와 남은 확인 사항](docs/EXHAUST-PATH-KO.md)

**직접 제어가 제공되지 않을 가능성도 있으며, 파일 추출이 제어 가능성을 보장하지는 않습니다.** 호출 인자와 응답, 실제 플랩 상태 확인, 순정 자동 제어로 돌리는 방법을 확인한 뒤 제어판을 구현합니다. 순정 자동 복귀가 검증되지 않으면 제어 ZIP을 게시하지 않습니다. 실제 동작과 재시작·제거 시 복귀는 해당 차량에서 별도로 검증해야 합니다.

## 개발과 검증

Python 3.10 이상으로 `python build.py --services`를 실행하면 `dist/`에 보완 추출 USB ZIP과 `SHA256SUMS.txt`를 만듭니다. `python build.py`는 전체 수집 프로필을 만듭니다. ZIP은 고정된 파일 목록으로 만들며 제조사 바이너리나 수집 결과를 포함하지 않습니다.

`python -m unittest discover -s tests -v`는 모의 헤드유닛에서 버전 거부, 추출 완료·누락·실패, 기존 결과 보존을 검증합니다. 셸 테스트에는 POSIX `sh`가 필요하며 Windows에서는 `TEST_SH`에 Git for Windows의 `sh.exe` 경로를 지정합니다. PC 테스트는 차량의 제어 가능성이나 실차 동작을 입증하지 않습니다.

## 근거

- [NEMESIS의 USB 스크립트 실행 규격](https://github.com/xwtk/hmg_nemesis/blob/main/06-Run-Scripts.md)
- [NEMESIS 패키지 규격](https://github.com/xwtk/hmg_nemesis/blob/main/05-Packages.md)
- [HMG-API 차량 명령 목록](https://github.com/Open-HMG/HMG-API/blob/5a642c5b47b5d9fc5e967603d764c39ba0b77dfd/docs/vehicle-commands.md): 확인 시점에 배기 플랩 명령은 없음.
- [HMG-API의 MICOM 인터페이스 설명](https://github.com/Open-HMG/HMG-API/blob/5a642c5b47b5d9fc5e967603d764c39ba0b77dfd/docs/micom-map.md): 내비 Android가 차량 CAN을 직접 보는 구조로 가정할 수 없음.

## License

이 저장소의 자체 작성 코드·문서는 MIT License입니다. NEMESIS나 HMG-API 코드를 복사하거나 배포하지 않습니다. 수집된 제조사 바이너리에는 이 라이선스가 적용되지 않습니다. 현대자동차 및 NEMESIS 공식 프로젝트와 무관한 커뮤니티 연구입니다.
