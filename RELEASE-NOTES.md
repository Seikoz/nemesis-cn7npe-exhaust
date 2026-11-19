CN7NPE 한국형 V039.001.260902용 **MICOM·HCAN 보완 추출 v0.3.0**입니다. NEMESIS 1.16.7 이상이 필요합니다.

**플랩 열림 / 닫힘 / 순정 자동 제어는 아직 구현되지 않았습니다.** 추가 하드웨어 없이 제어 가능한지 정적 분석하기 위한 파일 수집 도구입니다.

이번 분석에서 일반 MICOM 송신 인터페이스를 확인했습니다. 다만 MICOM 이후 엔진 ECU로의 전달과 AEV 강제 제어·해제 명령은 미확인입니다. [분석 근거](https://github.com/Seikoz/nemesis-cn7npe-exhaust/blob/main/docs/MICOM-SOFTWARE-PATH-KO.md)

- 자산: `NEMESIS-CN7NPE-Exhaust-Transport-Research-v0.3.0-USB.zip`. GitHub의 자동 Source code ZIP과 다릅니다.
- ZIP 전체를 USB 최상위에 풀고 주차 상태에서 연결하여 NEMESIS 실행 질문에 동의합니다. [사용법](https://github.com/Seikoz/nemesis-cn7npe-exhaust/blob/main/usb/INSTALL-TRANSPORT-KO.md)
- HCAN 확장 JAR/ODEX, Engineering 이름의 시스템 앱 ODEX, MICOM/HCAN/HSCAN 이름의 시스템 바이너리·라이브러리만 확인합니다. 50MB N 모드 APK는 다시 복사하지 않습니다.
- 파일당 8MiB, 복사 코드 합계 24MiB 제한이며 초과 파일은 건너뛰고 기록합니다. 이름이 맞지 않거나 제한에 걸린 파일은 추가 분석에 필요할 수 있습니다.
- 관련 서비스·프로세스·소켓 이름만 읽습니다. 차량 소켓 연결·MICOM/ECU 명령·시험 모드 진입·데몬 실행/중지·복사한 바이너리 실행·시스템 설정 변경은 하지 않습니다.
- 퍼센트·5단계·현재 파일·복사/없음 개수를 표시합니다. **100% 뒤 NEMESIS 완료 알림까지 확인하고** USB를 분리하세요.
- 최종 판정은 `result.txt`의 `collection=COMPLETE`입니다. 필수 HCAN ODEX 복사와 선택 대상 확인 완료이며, 모든 분석 입력 확보나 제어 성공은 아닙니다. `report.txt`의 `engineering_odex`, `native_files`, `skipped_files`도 확인합니다.
- 새 결과 폴더를 이 PC의 `C:\Users\User\Desktop\nemesis-cn7npe-exhaust\private\transport-extra`에 복사하면 업로드 없이 로컬 분석할 수 있습니다. 제조사 원본·결과 폴더는 공개 GitHub에 올리지 마세요.

모의 환경에서 파일 선택, 크기 제한, 오류 처리, 기존 결과 보존, USB ZIP 구조를 검증합니다. v0.3.0은 실차 미검증이며 기존 v0.2.1의 실차 추출 완료와 구분합니다. 커널 수준 USB 입출력 정지는 명령 제한보다 오래 걸릴 수 있습니다.
