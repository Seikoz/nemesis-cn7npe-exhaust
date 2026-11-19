# MICOM·HCAN 경로 보완 추출 v0.3.0

추가 하드웨어 없이 제어 가능한지 분석하기 위한 **파일 추출 도구**입니다. 플랩 제어 기능은 없습니다. 대상은 한국 CN7N PE `V039.001.260902`, TCC803x, NEMESIS 1.16.7 이상입니다.

1. ZIP 안의 모든 파일을 USB 최상위에 풉니다. 이 ZIP의 `NEMESIS.data`가 `collect-transport.sh`를 가리켜야 합니다. 이전 자료 수집용 `NEMESIS.data`를 섞지 마세요. 기존 결과 폴더는 보관합니다.
2. 주차 상태에서 USB를 연결하고 NEMESIS의 실행 질문에 예를 누릅니다.
3. 퍼센트·단계·현재 파일을 확인합니다. 퍼센트는 완료한 작업 단계 기준입니다.
4. **100% 뒤 NEMESIS 완료 알림까지 확인한 후** USB를 분리합니다.
5. 새 `CN7NPE-exhaust-private-N` 폴더를 `C:\Users\User\Desktop\nemesis-cn7npe-exhaust\private\transport-extra`에 복사해 주세요. 이 PC에 복사하면 대화에 ZIP을 업로드할 필요가 없습니다.

수집 대상은 `com.hkmc.ext.hcan.jar/odex`, Engineering 이름의 시스템 앱 ODEX, MICOM/HCAN/HSCAN 이름의 시스템 바이너리·라이브러리입니다. 50MB N 모드 APK는 다시 복사하지 않습니다. 파일당 8MiB, 복사하는 코드 합계 24MiB를 넘으면 해당 파일을 건너뛰고 보고서에 기록합니다. 전체 결과에는 작은 목록·진행 기록이 추가됩니다.

서비스·프로세스 목록에서 관련 이름과 `/proc/net/unix`의 관련 소켓 이름도 읽습니다. `/data` 파일, 연락처, VIN, 로그캣, 전체 getprop, 차량 통신 내용은 수집하지 않습니다. 소켓 연결·Binder 제어 호출·차량 명령·데몬 시작/정지·시험 모드 변경·앱 설치는 하지 않습니다. 복사한 바이너리를 실행하지 않습니다.

최종 판정은 `result.txt`의 `collection=COMPLETE`입니다. 이는 **필수 HCAN ODEX 복사 및 선택 대상 확인 완료**이며 모든 분석 입력 확보나 제어 성공을 뜻하지 않습니다. `report.txt`의 `engineering_odex`, `native_files`, `skipped_files`도 확인합니다. 필수 파일 누락·복사 실패·UI 실패·최종 저장 실패 때에는 완료로 처리하지 않습니다.

파일 크기 확인 15초, 복사 60초, 서비스/프로세스 목록 각 10초, USB 저장 마무리 60초 제한입니다. 소수 파일이면 보통 수분 안에 끝날 것으로 예상하지만, 소요 시간과 대상 차량 동작은 아직 실차 검증하지 않았습니다. 실패 시 생성된 폴더를 보관해 주세요.

추출 결과는 비공개 분석 자료입니다. GitHub 릴리스·이슈 등에 제조사 원본이나 결과 폴더를 올리지 마세요.
