#!/system/bin/sh
# Read three selected STOCK files. Never open a vehicle socket,
# execute copied binaries, issue Binder control calls, or touch system settings.
export PATH=/sbin:/vendor/bin:/system/sbin:/system/bin:/system/xbin
export LD_LIBRARY_PATH=/vendor/lib:/system/lib
umask 077
case "$0" in
    */*) USB_DIR=${0%/*} ;;
    *) USB_DIR=. ;;
esac
USB_DIR=$(cd "$USB_DIR" && pwd -P) || exit 1
case "$USB_DIR" in
    /storage/usb[0-9]|/mnt/media_rw/usb[0-9]) ;;
    *) echo "Run from a NEMESIS USB drive, not internal storage."; exit 1 ;;
esac
[ -f "$USB_DIR/CN7NPE-EXHAUST-RESEARCH.txt" ] || exit 1
[ -f "$USB_DIR/progress.sh" ] || exit 1
COLLECTOR_VERSION=0.3.1
. "$USB_DIR/progress.sh"
show_or_abort 0 "1/5 대상 확인" "HCAN 서비스 구현 파일 세 개만 확인합니다."
trap 'if [ -n "$CHILD_PID" ]; then kill -TERM "$CHILD_PID" 2>/dev/null; sleep 1; kill -KILL "$CHILD_PID" 2>/dev/null; wait "$CHILD_PID" 2>/dev/null; fi; progress_failure "실행 중단 신호를 받았습니다."; exit 130' INT TERM HUP
PRODUCT=$(getprop ro.build.product) || exit 1
case "$PRODUCT" in
    CN7NPE.KOR.0000.V039.001.260902|CN7NPE.KOR.S5W_M.V039.001.260902) ;;
    *) progress_failure "CN7NPE 한국형 V039.001.260902만 지원합니다."; exit 2 ;;
esac
[ "$(getprop ro.board.platform)" = tcc803x ] || {
    progress_failure "TCC803x 헤드유닛만 지원합니다."; exit 2;
}
INDEX=1
OUT=
while [ "$INDEX" -le 20 ]; do
    CANDIDATE="$USB_DIR/CN7NPE-exhaust-private-$INDEX"
    if mkdir "$CANDIDATE" 2>/dev/null; then OUT=$CANDIDATE; break; fi
    INDEX=$((INDEX + 1))
done
[ -n "$OUT" ] || { progress_failure "USB 결과 폴더를 만들 수 없습니다."; exit 3; }
mkdir "$OUT/stock" || { progress_failure "USB 저장 공간을 확인해 주세요."; exit 3; }
UI_LOG="$OUT/ui.log"
exec 2> "$OUT/collector-errors.log"
REPORT="$OUT/report.txt"
MANIFEST="$OUT/candidates.txt"
MAX_FILE_BYTES=8388608
MAX_TOTAL_BYTES=16777216
TOTAL_BYTES=0
SERVICE_JAR=0
SERVICE_CODE=0
JNI_CODE=0
{
    echo "CN7NPE exhaust HCAN service collector $COLLECTOR_VERSION"
    echo "profile=hcan-service"
    echo "flap_control=NOT_IMPLEMENTED"
    echo "product=$PRODUCT"
    echo "platform=tcc803x"
    echo "stock_file_limit_bytes=$MAX_FILE_BYTES"
    echo "stock_total_limit_bytes=$MAX_TOTAL_BYTES"
    echo "Stock files are private analysis inputs."
} > "$REPORT" || exit 3
show_or_abort 5 "1/5 대상 확인" "새 결과 폴더 생성 · 파일당 8MiB / 코드 합계 16MiB 제한"

# Exact paths identified by framework2 Loader/HkmcSystemServer analysis.
# No directory scanning, old extractions, firmware dump, or runtime IPC.
{
    echo /system/framework/com.infobank.jar
    echo /system/framework/com.infobank.odex
    echo /system/lib/libautoframework_jni.so
} > "$MANIFEST" || exit 3
SLOTS=0
while IFS= read -r SOURCE; do SLOTS=$((SLOTS + 1)); done < "$MANIFEST"
CHECKED=0
while IFS= read -r SOURCE; do
    CHECKED=$((CHECKED + 1))
    PARENT=${SOURCE%/*}
    case "$SOURCE" in /system/*) ROOT_NAME=system ;; /vendor/*) ROOT_NAME=vendor ;; esac
    DEST="${ROOT_NAME}_${PARENT##*/}_${SOURCE##*/}"
    show_or_abort $((10 + (CHECKED - 1) * 65 / SLOTS)) "2/5 통신 코드 수집" "현재: ${SOURCE##*/} · $CHECKED/$SLOTS"
    if [ -L "$SOURCE" ]; then
        echo "skipped_symlink=$SOURCE" >> "$REPORT"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    if [ ! -f "$SOURCE" ] || [ ! -r "$SOURCE" ]; then
        echo "missing=$SOURCE" >> "$REPORT"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    # KitKat toolbox has ls, but not wc/tr/stat. Android ls -ln omits the
    # link-count column; GNU ls has it. Both formats are checked explicitly.
    if ! run_bounded 15 ls -ln "$SOURCE" > "$OUT/size.tmp"; then
        echo "collection=FAILED_SIZE_CHECK" >> "$REPORT"
        progress_failure "파일 크기를 확인하지 못했습니다: ${SOURCE##*/}"
        exit 4
    fi
    read -r MODE COL2 COL3 COL4 COL5 REST < "$OUT/size.tmp"
    case "$MODE" in
        -*) ;;
        *) echo "collection=FAILED_SIZE_FORMAT" >> "$REPORT"; progress_failure "일반 파일 크기 형식 오류"; exit 4 ;;
    esac
    case "$COL5" in
        ''|*[!0-9]*)
            case "$COL5" in
                ????-??-??) FILE_BYTES=$COL4 ;;
                *) echo "collection=FAILED_SIZE_FORMAT" >> "$REPORT"; progress_failure "파일 날짜·크기 형식 오류"; exit 4 ;;
            esac ;;
        *) FILE_BYTES=$COL5 ;;
    esac
    case "$FILE_BYTES" in
        ''|*[!0-9]*) echo "collection=FAILED_SIZE_FORMAT" >> "$REPORT"; progress_failure "파일 크기 형식 오류"; exit 4 ;;
    esac
    if [ "$FILE_BYTES" -eq 0 ]; then
        echo "skipped_empty=$SOURCE" >> "$REPORT"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    if [ "$FILE_BYTES" -gt "$MAX_FILE_BYTES" ] ||
       [ "$FILE_BYTES" -gt $((MAX_TOTAL_BYTES - TOTAL_BYTES)) ]; then
        echo "skipped_size_limit=$SOURCE bytes=$FILE_BYTES" >> "$REPORT"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    if ! run_bounded 60 cp "$SOURCE" "$OUT/stock/$DEST"; then
        echo "collection=FAILED_COPY" >> "$REPORT"
        progress_failure "파일 복사 실패 또는 60초 시간 초과: ${SOURCE##*/}"
        exit 4
    fi
    TOTAL_BYTES=$((TOTAL_BYTES + FILE_BYTES))
    COPIED=$((COPIED + 1))
    echo "copied=$SOURCE -> stock/$DEST bytes=$FILE_BYTES" >> "$REPORT"
    case "$SOURCE" in
        /system/framework/com.infobank.jar) SERVICE_JAR=1 ;;
        /system/framework/com.infobank.odex) SERVICE_CODE=1 ;;
        /system/lib/libautoframework_jni.so) JNI_CODE=1 ;;
    esac
done < "$MANIFEST"
rm -f "$OUT/size.tmp"

# Only local result bookkeeping after the three fixed paths were checked.
show_or_abort 77 "3/5 서비스 구현 확인" "Infobank JAR·ODEX 확보 여부를 확인합니다."
{
    echo "service_jar=$SERVICE_JAR"
    echo "service_odex=$SERVICE_CODE"
    echo "jni_library=$JNI_CODE"
    echo "stock_copied_bytes=$TOTAL_BYTES"
    echo "copied_files=$COPIED"
    echo "skipped_files=$SKIPPED"
    echo "JNI library is optional. COMPLETE is extraction status, not vehicle control."
} >> "$REPORT"
show_or_abort 85 "4/5 누락 확인" "JNI 라이브러리는 없을 수 있습니다. 누락 여부를 기록합니다."
show_or_abort 95 "5/5 결과 확인" "필수 Infobank JAR·ODEX와 파일 크기 제한을 확인합니다."
if [ "$SERVICE_JAR" -ne 1 ] || [ "$SERVICE_CODE" -ne 1 ]; then
    echo "collection=INCOMPLETE" >> "$REPORT"
    progress_report_status INCOMPLETE
    progress_failure "필수 Infobank JAR 또는 ODEX가 없습니다. 부분 결과 폴더를 보관해 주세요."
    exit 4
fi
cat > "$OUT/PRIVATE-README.txt" <<'PRIVATE'
추가 하드웨어 없는 제어 가능성을 분석하기 위한 정적 코드 추출입니다.
플랩 제어·MICOM 송신·진단 명령·시험 모드 진입은 하지 않았습니다.
COMPLETE는 필수 Infobank JAR·ODEX 복사와 선택 JNI 파일 확인 완료를 뜻합니다.
report.txt의 service_jar/service_odex/jni_library/skipped_files도 확인해 주세요.
제조사 원본·추출 결과는 공개 GitHub에 올리지 마세요.
이 결과 폴더를 PC의 프로젝트 private 폴더 아래에 복사해 주세요.
PRIVATE
[ "$?" -eq 0 ] || exit 3
show_or_abort 99 "5/5 USB 저장 마무리" "쓰기 완료 확인 · 제한 60초 · 완료 알림까지 기다리세요."
progress_finish || exit 4
echo "Collection complete. Exhaust flap control is not implemented."
exit 0
