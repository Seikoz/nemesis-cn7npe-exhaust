# CN7NPE 차량 서비스 보완 추출 v0.2.1

기존 추출 자료가 있는 분을 위한 **보완 추출**입니다. 50MB N 모드 APK는 다시 복사하지 않습니다. 플랩 제어 기능은 없습니다.

대상: CN7NPE KOR V039.001.260902, TCC803x, NEMESIS 1.16.7 이상.

1. ZIP의 모든 파일을 USB 최상위에 풉니다. `NEMESIS.data`와 `collect-services.sh`, `collect.sh`, `progress.sh`가 함께 있어야 합니다. 기존 결과 폴더는 보관하세요.
2. 주차 상태에서 USB를 연결하고 NEMESIS의 스크립트 실행 질문에 예를 누릅니다.
3. `automotive-service.jar`와 `automotive-service.odex`만 확인·복사합니다. 퍼센트는 작업 단계 기준이며 바이트나 시간 기준이 아닙니다.
4. **100% 다음 NEMESIS 완료 알림까지 확인하고** USB를 분리합니다. 99%에서 저장 마무리를 기다릴 수 있습니다.
5. 새 `CN7NPE-exhaust-private-N` 폴더를 이 PC의 `C:\Users\User\Desktop\nemesis-cn7npe-exhaust\private` 아래에 복사하고 폴더 이름을 알려 주세요. 이 PC에 있으면 대화에 업로드할 필요가 없습니다.

최종 판정은 **`result.txt`**의 `collection=COMPLETE`입니다. `report.txt`는 복사 목록이며 `READY_TO_SYNC`는 아직 최종 판정이 아닙니다. 0.2.0에서 실패한 보고서 재작성·교체 절차 대신 작은 최종 결과 파일을 따로 저장하도록 바꿨습니다. 실패 원인이 이 절차 때문인지는 아직 확인되지 않았습니다.

오류가 나면 결과 폴더를 그대로 보관하세요. `progress.txt`, `events.log`, `collector-errors.log`와 프레임워크 파일 이름 목록 `framework-files.txt`가 진단에 필요합니다. 필수 ODEX가 없으면 완료 처리하지 않습니다.

각 복사와 USB 저장 마무리는 60초 제한입니다. 진행 화면 호출은 5초 제한입니다. 커널 수준의 USB 입출력 정지는 종료를 지연시킬 수 있습니다. 실차 재검증은 아직 하지 않았습니다.

시스템 파일 변경·플랩 조작·앱 설치·재부팅은 하지 않습니다. 추출된 제조사 파일을 공개 GitHub에 업로드하지 마세요.
