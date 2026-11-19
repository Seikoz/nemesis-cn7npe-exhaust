# 추가 하드웨어 없는 AEV 제어 경로 조사

분석일: 2026-11-19. 대상: 한국 CN7N PE `CN7NPE.KOR.0000.V039.001.260902`.

**Android에서 일반 MICOM 메시지를 송신하는 인터페이스를 확인했습니다. 따라서 추가 하드웨어 없는 제어를 불가능하다고 단정할 수는 없습니다. 그러나 MICOM에서 엔진 ECU로 AEV 강제 제어를 전달하는 경로와 명령은 아직 확인되지 않았습니다.**

이 문서는 추출한 `automotive.odex`, `automotive-service.odex`와 v0.3.0 보완 추출의 HCAN 확장·Engineering Mode·네이티브 데몬을 정적으로 분석한 결과입니다. 관련 Java 클래스는 API 17로 deodex·재조립 후 JADX에서 분석했습니다. Engineering Mode 전체 deodex에는 한 클래스의 해석 오류가 있어, 아래 결론에 사용하는 관련 클래스를 별도로 추출하여 오류 없이 재처리했습니다. 실차에서 Binder 호출, MICOM 송신, ECU 진단, 파형 측정은 수행하지 않았습니다. 기존 원본 해시는 [기존 분석](EXHAUST-PATH-KO.md)에 기록되어 있습니다.

## 경로별로 확인한 범위

| 경로 | 정적 분석에서 확인한 구현 | AEV 직접 제어 판단 |
| --- | --- | --- |
| `NModeManager → SystemService` | 순정 개별 주행모드 설정을 MICOM으로 전달 | 배기음 단계 설정이며 강제 열림/닫힘/제어 해제는 미확인 |
| `IMicomDataService.sendMicomData()` | 송신·수신 모듈, 타입, 기능 두 바이트, 데이터 배열을 `MicomService → MicomPacketRunner`로 전달 | 일반 MICOM 메시지 송신 계층 존재. 엔진 ECU 진단 중계의 증거는 아님 |
| `EngineeringMode.requestDiagnose() → EngineeringModeService` | DTC 목록을 항목당 두 바이트로 변환하고 서비스에 위임 | 확인한 순정 호출부는 DTC 요청. AEV 액추에이터 시험은 미확인 |
| `SystemService.requestDiagnose()` | MICOM 진단 모듈의 정보 요청 기능으로 바이트 배열 전달 | 임의 ECU 주소·CAN ID·UDS 요청을 전달하는 API로 검증되지 않음 |
| `HscanMicomService.sendPacket()` | MICOM 준비 여부를 확인한 뒤 같은 MICOM 송신 계층으로 위임 | CAN 프레임을 직접 송신하는 구현으로 볼 근거 없음 |
| `TM_HSCANAdapter` | `requestDiag()`·`setCanSignalValue()`를 `tm_hscan_service`에 위임 | 클라이언트 프록시 확인. 서비스 실제 처리부와 AEV 항목은 미확인 |
| `micomd` | 로컬 MICOM 메시지를 큐에 넣고 TTY로 기록하는 경로 확인 | Android 이후 UART 전달까지 추적. MICOM 펌웨어의 ECU 라우팅은 미확인 |
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

보완 추출에서 `EngineeringMode.requestDiagnose(int[], int)`와 `DtcFormatExt`를 확인했습니다. 정수 DTC 목록을 문자열 형식으로 바꾼 뒤 각 DTC를 두 바이트로 구성하여 연속 배열로 전달합니다. Engineering Mode 앱의 `DTCServiceUtil`은 스피커·안테나 등 진단 대상의 DTC 목록으로 이 API를 호출합니다. **확인한 순정 사용법은 DTC 목록 요청이며, 임의 엔진 ECU 주소와 UDS 프레임을 전달하는 구현으로 검증되지 않았습니다.** 난독화 필드 이름 `aEv`는 이 DTC 목록에도 사용되므로, 이름만 보고 Active Exhaust Valve로 해석하지 않습니다.

## HCAN 보완 추출에서 확인한 내용

`HscanMicomService`에는 MICOM 준비 시 `hscand`를 시작하는 코드가 있습니다. 이벤트는 HSCAN/telematics 계열의 MICOM 카테고리를 수신하여 리스너로 전달하며, 송신은 다시 `MicomService.sendPacket()`을 사용합니다. **이 시작 코드를 분석했을 뿐, 이번 연구 도구가 데몬을 시작한 것은 아닙니다.**

v0.3.0 결과에는 `com.hkmc.ext.hcan.jar/.odex`, `HKMC_EngineerMode.odex`, `hscand`, `micomd`, `micomlog`가 모두 포함됐습니다. 추출 상태는 `100% COMPLETE`, 복사 6개, 건너뜀 0개, 오류 로그 0바이트이며 코드 합계는 1,953,353바이트입니다. 대상 펌웨어도 기존 분석과 일치합니다. 이는 추출 성공이며 플랩 제어 시험 성공이 아닙니다.

HCAN 확장의 `TM_HSCANAdapter`는 등록된 `tm_hscan_service`의 `ITM_HSCANService`를 사용하는 클라이언트입니다.

- `requestDiag()`는 진단 타입·콜백·호출 앱 이름을 서비스로 전달합니다. 실제 하위 진단 절차는 프록시에 없습니다.
- `cancelReqDiag()`는 리스너 등록 해제에 위임합니다. ECU의 액추에이터 제어권 해제 명령이라고 볼 수 없습니다.
- `setCanSignalValue()`도 서비스 호출입니다. 인접한 `CAN_SIGNAL_TYPE` 상수는 속도·RPM·주행거리·등록 상태 항목이며, AEV 강제 개폐 항목은 확인되지 않았습니다. 이 상수 목록이 모든 하위 기능을 설명한다고 단정하지 않습니다.
- 수집된 HCAN 확장과 검사한 프레임워크의 메서드·클래스 목록에서는 이 서비스의 실제 처리 구현을 확인하지 못했습니다. 실제 서비스 등록은 수집 목록에서 확인했으나, 등록만으로 구현 파일이나 제어 범위를 알 수는 없습니다.

이후 기존 `framework2.odex`의 문자열 참조를 추적해 **HCAN 서비스 구현을 로드하는 위치를 확인했습니다.** `com.hkmc.internal.server.HkmcSystemServer`는 `Loader.getInfobankJar()`를 사용하여 `com.hkmc.telematics.hscan.TM_HSCANService`를 불러오고, Context 생성자를 통해 인스턴스를 만들어 시스템 준비 단계에서 사용합니다.

`Loader`의 Infobank 클래스 경로는 기존 `automotive.jar`와 **`/system/framework/com.infobank.jar`**의 조합입니다. 이미 검사한 automotive 코드에는 해당 구현 클래스가 없으며, 기존 파일 목록에는 `com.infobank.jar`와 `com.infobank.odex`가 모두 존재합니다. 따라서 이 두 파일이 다음 분석 대상입니다. 이는 APK 이름 추측이나 전체 앱 검색이 아니라 대상 펌웨어의 로더 코드에서 좁힌 경로입니다. 실제 서비스 등록과 메서드 본문은 이 파일을 확보한 뒤 확인해야 합니다.

같은 Loader는 Infobank의 JNI 경로 값으로 `/system/lib/libautoframework_jni.so`를 사용합니다. 이 때문에 해당 라이브러리를 선택 수집 대상으로 포함했습니다. **이 경로 값만으로 HCAN 진단이 JNI를 반드시 통한다거나 라이브러리 안에 ECU 중계가 있다고 확정하지 않습니다.**

이번 로더 분석은 framework2를 API 17로 deodex한 뒤 관련 두 클래스를 재조립하고 JADX 결과와 smali를 대조했습니다. 해당 deodex 로그에는 오류가 없었습니다. OEM 원본과 복원 코드는 공개하지 않습니다.

## 네이티브 전달 경로와 한계

`micomd`의 ARM 코드를 분석하여 클라이언트 메시지 수신·프레임 분리·송신 큐·TTY 기록으로 이어지는 경로를 확인했습니다. 시작 코드의 기본 TTY는 `/dev/ttyTCC2`이며, 장치를 열어 저장한 파일 디스크립터를 송신 큐의 기록 경로가 사용합니다. 이 분석은 바이너리를 PC에서 읽어 수행했으며, 장치를 열거나 데몬을 실행하지 않았습니다.

이는 앞서 확인한 `MicomPacketRunner → micom_mux` 이후의 전달 계층을 설명합니다. **UART에 전달되는 MICOM 메시지가 엔진 ECU의 어떤 요청으로 변환되는지는 이 데몬에서 확인하지 못했습니다.** 일반 MICOM 송신, 차량 CAN 송신, AEV 강제 제어는 각각 별도 증거가 필요합니다.

`hscand`에는 `hscan_mux`, `micom_mux_albumart`, `/dev/tcc-tsif0`와 관련 입출력 코드가 있습니다. 이 이름이나 장치 접근만으로 임의 CAN/UDS 송신 기능을 입증할 수 없습니다. 또한 `micomlog`에는 소켓 송신과 MICOM 로그 설정 요청 코드가 있어 단순 수동 로그 읽기 도구로 취급하지 않으며 실행하지 않았습니다.

## 공개 구현 대조

[HMG-API MICOM 설명](https://github.com/Open-HMG/HMG-API/blob/main/docs/micom-map.md)과 [MicomWatch 구현](https://github.com/Open-HMG/HMG-API/blob/main/core/runtime/java/hmgapi/vehicle/MicomWatch.java)은 차량의 MICOM 데이터 서비스에 콜백을 등록해 메시지를 관찰하는 방식을 사용합니다. [차량 명령 목록](https://github.com/Open-HMG/HMG-API/blob/main/docs/vehicle-commands.md)에서 배기 플랩 제어는 확인되지 않았습니다. 해당 프로젝트가 자체 CAN 송신을 제공하지 않는다는 운영 방침은, 대상 차량 전체에 송신 경로가 없다는 증거가 아닙니다.

다른 차종·다른 세대의 `micomd` 도구나 UDS 예제를 대상 차량의 실행 명령으로 가져오지 않습니다. 일반 UDS의 제어 해제 개념이 있어도 해당 ECU의 식별자·조건·전송 경로를 검증해야 합니다.

## v0.3.0 보완 추출과 남은 한계

[MICOM·HCAN 보완 추출 사용법](../usb/INSTALL-TRANSPORT-KO.md)은 위에서 부족한 **정적 코드와 관련 서비스·프로세스·소켓 이름**만 수집합니다. 차량 통신 소켓에 연결하거나 메시지를 보내지 않습니다. 복사한 바이너리도 실행하지 않습니다.

이번에는 큰 N 모드 APK를 다시 복사하지 않으며, 파일당 8MiB·복사 코드 합계 24MiB로 제한합니다. Android 4.4 기본 toolbox에 없는 `wc`/`tr`/`stat`에 의존하지 않고 `ls -ln`의 크기 필드를 확인합니다. Android와 GNU의 출력 차이를 모의 테스트로 검증합니다. 기본 도구 목록과 출력 형식은 [AOSP KitKat toolbox](https://github.com/aosp-mirror/platform_system_core/blob/android-4.4.2_r1/toolbox/Android.mk), [ls 구현](https://github.com/aosp-mirror/platform_system_core/blob/android-4.4.2_r1/toolbox/ls.c)을 대조했습니다.

보완 추출로 **내비의 MICOM 송신 계층에서 네이티브 UART 전달까지** 확인 범위를 넓혔습니다. 그러나 HCAN 서비스의 실제 처리부, MICOM 펌웨어의 ECU 중계, 대상 AEV의 강제 열림·닫힘·제어 해제 명령과 피드백은 아직 확인되지 않았습니다. 추가 하드웨어 없는 제어의 가능성은 미확정이며, 세 가지 AEV 제어를 제공하는 패키지는 아직 구현하지 않았습니다.

## v0.3.1: 확인된 구현 컨테이너만 추가 수집

[HCAN 서비스 보완 추출 안내](../usb/INSTALL-HCAN-SERVICE-KO.md)의 새 프로필은 `com.infobank.jar`, `com.infobank.odex`, 선택 파일 `libautoframework_jni.so`의 **고정된 세 경로만** 확인합니다. 이미 받은 파일은 반복 수집하지 않으며, 디렉터리 검색·서비스 목록·프로세스 목록·MICOM 펌웨어 덤프는 하지 않습니다. 파일당 8MiB, 복사 합계 16MiB 제한입니다.

Infobank 코드가 확보되면 `tm_hscan_service` 등록, `requestDiag`와 `setCanSignalValue`의 실제 분기·권한 검사, MICOM 헤더·응답 처리, 하위 JNI 사용 여부를 확인합니다. 여기서도 ECU 중계나 AEV 기능이 드러나지 않으면 그 부분은 미확인으로 남깁니다. MICOM 플래시 읽기나 부트로더 진입을 이 수집기로 시도하지 않습니다.
