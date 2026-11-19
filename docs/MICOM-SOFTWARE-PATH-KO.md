# 추가 하드웨어 없는 AEV 제어 경로 조사

분석일: 2026-11-19. 대상: 한국 CN7N PE `CN7NPE.KOR.0000.V039.001.260902`.

**Android에서 일반 MICOM 메시지를 송신하는 인터페이스를 확인했습니다. 따라서 추가 하드웨어 없는 제어를 불가능하다고 단정할 수는 없습니다. 그러나 MICOM에서 엔진 ECU로 AEV 강제 제어를 전달하는 경로와 명령은 아직 확인되지 않았습니다.**

이 문서는 추출한 `automotive.odex`와 `automotive-service.odex`의 정적 분석입니다. 새로 조사한 클래스는 API 17로 deodex·재조립 후 JADX에서 분석했으며 deodex·조립 로그 오류 없이 완료했습니다. 실차에서 Binder 호출, MICOM 송신, ECU 진단, 파형 측정은 수행하지 않았습니다. 원본 해시는 [기존 분석](EXHAUST-PATH-KO.md)에 기록되어 있습니다.

## 경로별로 확인한 범위

| 경로 | 정적 분석에서 확인한 구현 | AEV 직접 제어 판단 |
| --- | --- | --- |
| `NModeManager → SystemService` | 순정 개별 주행모드 설정을 MICOM으로 전달 | 배기음 단계 설정이며 강제 열림/닫힘/제어 해제는 미확인 |
| `IMicomDataService.sendMicomData()` | 송신·수신 모듈, 타입, 기능 두 바이트, 데이터 배열을 `MicomService → MicomPacketRunner`로 전달 | 일반 MICOM 메시지 송신 계층 존재. 엔진 ECU 진단 중계의 증거는 아님 |
| `EngineeringModeService.requestDiagnose()` | 호출 식별자를 정리한 뒤 `SystemService.requestDiagnose()`에 위임 | payload 의미와 MICOM 이후 처리는 미확인 |
| `SystemService.requestDiagnose()` | MICOM 진단 모듈의 정보 요청 기능으로 바이트 배열 전달 | 임의 ECU 주소·CAN ID·UDS 요청을 전달하는 API로 검증되지 않음 |
| `HscanMicomService.sendPacket()` | MICOM 준비 여부를 확인한 뒤 같은 MICOM 송신 계층으로 위임 | CAN 프레임을 직접 송신하는 구현으로 볼 근거 없음. `hscand`와 HCAN 확장 분석 필요 |
| `setCanTestOnOff()` / `setVehicleInterfaceOnOff()` | 테스트/차량 인터페이스 상태를 바꾸는 별도 요청 | ECU 주소·데이터를 받는 중계 API나 AEV 명령으로 확인되지 않음. 실행하지 않음 |

## 일반 MICOM 송신 인터페이스

대상 프레임워크에는 `IMicomDataService`와 그 Binder Stub/Proxy가 있으며, `sendMicomData`는 다섯 개의 헤더 바이트와 데이터 배열을 받습니다. 서비스 이름 상수는 `com.hkmc.micom.micomdata`입니다.

`MicomService.sendMicomData()` 구현은 헤더 바이트 범위를 확인하고 전달 인자를 기록한 뒤, 같은 값으로 내부 `sendPacket()`을 호출합니다. 그 내부 메서드는 `MicomPacketRunner`로 위임하며, Runner는 로컬 소켓 `micom_mux`의 출력 스트림에 MICOM 형식의 메시지를 기록합니다.

확인한 해당 송신 메서드와 Stub에는 `SystemService.checkCallingPid()` 같은 명시적 호출자 검사가 없습니다. **이것이 NEMESIS 실행 환경에서 실제 호출 가능하다는 검증은 아닙니다.** 서비스 등록·SELinux/Binder 정책·실행 UID·소켓 정책과 하위 데몬/MICOM의 허용 범위는 별도로 확인해야 합니다.

또한 이 헤더의 모듈 ID·기능 번호는 차량 CAN ID와 다릅니다. 일반 메시지를 구성할 수 있는 Java 인터페이스가 있다고 해서, 그 데이터 배열에 CAN ID나 UDS 바이트를 넣으면 그대로 엔진 ECU로 전송된다고 가정할 수 없습니다.

## 진단 API 이름의 함정

`SystemService.requestDiagnose()`는 내부 호출자 PID 검사 후 진단 모듈로 전달합니다. 같은 펌웨어의 프로토콜 상수에서 해당 기능은 `CAN_DIAG_MICOM_INFO_C_REQ`, 응답은 `CAN_DIAG_MICOM_INFO_M_RESP`로 명명되어 있습니다. 주변 기능도 내비 시스템 버전, 모뎀 정보, 진단 정보 응답 등을 처리합니다.

직접 `SystemService`를 Binder로 부르는 것과 Engineering Mode 서비스를 통하는 것은 호출 경로가 다릅니다. Engineering Mode의 wrapper는 `Binder.clearCallingIdentity()` 뒤 위임하고, 수신 응답은 Engineering 리스너 및 ModeManager 쪽으로 전달합니다. 따라서 직접 호출 제한 하나만으로 상위 경로 전체가 막혔다고 결론 내리지 않습니다. 반대로 wrapper 존재만으로 ECU 진단 클라이언트라고 단정하지 않습니다.

**`responseDiagStopReq()`도 AEV 자동 복귀 명령이 아닙니다.** `CAN_DIAG_CPU_DIAG_STOP_M_REQ` 수신 경로가 내비 쪽 진단 중지 요청을 알리고, `responseDiagStopReq()`는 `CAN_DIAG_CPU_DIAG_STOP_C_RESP`를 보내는 구조입니다. 플랩 제어 소유권을 ECU에 되돌리는 기능으로 확인하지 못했습니다.

`resetIndividualDriveModeInstance()`의 캐시 초기화, Factory `RunSoundControl` ACK도 기존 분석과 같이 AEV 강제 제어 또는 해제 근거로 사용하지 않습니다.

## HCAN 쪽이 다음 확인 대상인 이유

`HscanMicomService`에는 MICOM 준비 시 `hscand`를 시작하는 코드가 있습니다. 이벤트는 HSCAN/telematics 계열의 MICOM 카테고리를 수신하여 리스너로 전달하며, 송신은 다시 `MicomService.sendPacket()`을 사용합니다. **이 시작 코드를 분석했을 뿐, 이번 연구 도구가 데몬을 시작한 것은 아닙니다.**

보완 추출 결과의 `framework-files.txt`에는 `com.hkmc.ext.hcan.jar` 및 `.odex`가 실제로 열거되어 있지만, 현재 PC의 추출본에는 이 두 파일이 없습니다. 또한 `hscand`·`micomd` 등 네이티브 코드와 Engineering Mode 앱의 진단 요청 생성부도 확보하지 못했습니다.

다음에는 이 코드에서 다음을 확인합니다.

- ECU 대상 주소/전송 채널/길이/타임아웃을 받는 인터페이스가 있는지, 아니면 정해진 차량 데이터 항목만 다루는지.
- `requestDiagnose()`에 전달되는 데이터의 실제 생성·해석 방식과 지원 항목.
- 네이티브 데몬이 MICOM 헤더를 어떻게 라우팅하는지, CAN/UDS 중계 또는 허용 목록이 있는지.
- AEV 강제 열림·닫힘·해제와 실제 피드백을 나타내는 기능이 존재하는지.

## 공개 구현 대조

[HMG-API MICOM 설명](https://github.com/Open-HMG/HMG-API/blob/main/docs/micom-map.md)과 [MicomWatch 구현](https://github.com/Open-HMG/HMG-API/blob/main/core/runtime/java/hmgapi/vehicle/MicomWatch.java)은 차량의 MICOM 데이터 서비스에 콜백을 등록해 메시지를 관찰하는 방식을 사용합니다. [차량 명령 목록](https://github.com/Open-HMG/HMG-API/blob/main/docs/vehicle-commands.md)에서 배기 플랩 제어는 확인되지 않았습니다. 해당 프로젝트가 자체 CAN 송신을 제공하지 않는다는 운영 방침은, 대상 차량 전체에 송신 경로가 없다는 증거가 아닙니다.

다른 차종·다른 세대의 `micomd` 도구나 UDS 예제를 대상 차량의 실행 명령으로 가져오지 않습니다. 일반 UDS의 제어 해제 개념이 있어도 해당 ECU의 식별자·조건·전송 경로를 검증해야 합니다.

## v0.3.0 보완 추출과 남은 한계

[MICOM·HCAN 보완 추출 사용법](../usb/INSTALL-TRANSPORT-KO.md)은 위에서 부족한 **정적 코드와 관련 서비스·프로세스·소켓 이름**만 수집합니다. 차량 통신 소켓에 연결하거나 메시지를 보내지 않습니다. 복사한 바이너리도 실행하지 않습니다.

이번에는 큰 N 모드 APK를 다시 복사하지 않으며, 파일당 8MiB·복사 코드 합계 24MiB로 제한합니다. Android 4.4 기본 toolbox에 없는 `wc`/`tr`/`stat`에 의존하지 않고 `ls -ln`의 크기 필드를 확인합니다. Android와 GNU의 출력 차이를 모의 테스트로 검증합니다. 기본 도구 목록과 출력 형식은 [AOSP KitKat toolbox](https://github.com/aosp-mirror/platform_system_core/blob/android-4.4.2_r1/toolbox/Android.mk), [ls 구현](https://github.com/aosp-mirror/platform_system_core/blob/android-4.4.2_r1/toolbox/ls.c)을 대조했습니다.

새 파일들을 분석해도 MICOM 펌웨어 내부까지 자동으로 밝혀지는 것은 아닙니다. 하위 라우팅이 펌웨어에만 있으면 그 부분은 여전히 미확인으로 남습니다. 현재 확인된 결론은 **내비의 일반 MICOM 송신 계층 존재까지**이며, 세 가지 AEV 제어를 제공하는 패키지는 아직 구현하지 않았습니다.
