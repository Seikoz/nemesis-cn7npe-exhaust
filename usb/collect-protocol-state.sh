#!/system/bin/sh
# Read only the saved diagnostic protocol-selection cache. Never open a vehicle socket,
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
COLLECTOR_VERSION=0.3.2-local
. "$USB_DIR/progress.sh"
show_or_abort 0 "1/5 대상 확인" "저장된 진단 프로토콜 선택 파일만 확인합니다."
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
mkdir "$OUT/state" || { progress_failure "USB 저장 공간을 확인해 주세요."; exit 3; }
UI_LOG="$OUT/ui.log"
exec 2> "$OUT/collector-errors.log"
REPORT="$OUT/report.txt"
MANIFEST="$OUT/candidates.txt"
MAX_FILE_BYTES=4096
MAX_TOTAL_BYTES=8192
TOTAL_BYTES=0
STATE_FILES=0
{
    echo "CN7NPE exhaust protocol state collector $COLLECTOR_VERSION"
    echo "profile=protocol-state"
    echo "flap_control=NOT_IMPLEMENTED"
    echo "product=$PRODUCT"
    echo "platform=tcc803x"
    echo "state_file_limit_bytes=$MAX_FILE_BYTES"
    echo "state_total_limit_bytes=$MAX_TOTAL_BYTES"
    echo "Protocol selection cache is a private analysis input; no ECU request is sent."
} > "$REPORT" || exit 3
show_or_abort 5 "1/5 대상 확인" "새 결과 폴더 생성 · 파일당 4KiB / 합계 8KiB 제한"

# Two exact roots used by stock DiagDefne/DiagProtocolManager.
# Do not list directories, inspect other /data files, or create the cache.
{
    echo /data/misc/infobank/diagInfo/DiagProtocalType.dat
    echo /securedata/misc/infobank/diagInfo/DiagProtocalType.dat
} > "$MANIFEST" || exit 3
SLOTS=0
while IFS= read -r SOURCE; do SLOTS=$((SLOTS + 1)); done < "$MANIFEST"
CHECKED=0
while IFS= read -r SOURCE; do
    CHECKED=$((CHECKED + 1))
    PARENT=${SOURCE%/*}
    case "$SOURCE" in /data/*) ROOT_NAME=data ;; /securedata/*) ROOT_NAME=securedata ;; esac
    DEST="${ROOT_NAME}_${PARENT##*/}_${SOURCE##*/}"
    show_or_abort $((10 + (CHECKED - 1) * 65 / SLOTS)) "2/5 프로토콜 캐시 확인" "현재: ${SOURCE##*/} · $CHECKED/$SLOTS"
    LINK_FOUND=0
    CHECK_PATH=$SOURCE
    while [ "$CHECK_PATH" != / ]; do
        if [ -L "$CHECK_PATH" ]; then LINK_FOUND=1; break; fi
        CHECK_PATH=${CHECK_PATH%/*}
        [ -n "$CHECK_PATH" ] || CHECK_PATH=/
    done
    if [ "$LINK_FOUND" -eq 1 ]; then
        echo "skipped_symlink_path=$SOURCE" >> "$REPORT"
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
    if ! run_bounded 60 cp "$SOURCE" "$OUT/state/$DEST"; then
        echo "collection=FAILED_COPY" >> "$REPORT"
        progress_failure "파일 복사 실패 또는 60초 시간 초과: ${SOURCE##*/}"
        exit 4
    fi
    TOTAL_BYTES=$((TOTAL_BYTES + FILE_BYTES))
    COPIED=$((COPIED + 1))
    echo "copied=$SOURCE -> state/$DEST bytes=$FILE_BYTES" >> "$REPORT"
    STATE_FILES=$((STATE_FILES + 1))
done < "$MANIFEST"
rm -f "$OUT/size.tmp"

# A missing/unknown cache is useful evidence. Never trigger diagnostics to fill it.
show_or_abort 77 "3/5 수집 상태 확인" "파일이 없어도 ECU 진단을 시작하지 않습니다."
{
    echo "protocol_state_files=$STATE_FILES"
    echo "state_copied_bytes=$TOTAL_BYTES"
    echo "copied_files=$COPIED"
    echo "skipped_files=$SKIPPED"
    if [ "$STATE_FILES" -gt 0 ]; then
        echo "protocol_state=AVAILABLE_FOR_OFFLINE_DECODE"
    else
        echo "protocol_state=UNAVAILABLE"
    fi
    echo "ECU_exchange=NOT_TESTED"
    echo "Cache records a saved selection, not a current ECU response."
} >> "$REPORT"
show_or_abort 85 "4/5 결과 구분" "완료는 경로 확인 완료입니다. 캐시 유무는 report.txt에 기록합니다."
show_or_abort 95 "5/5 결과 확인" "원본 변경 없이 USB에만 결과를 저장합니다."
cat > "$OUT/PRIVATE-README.txt" <<'PRIVATE'
진단 프로토콜 선택 캐시의 고정 경로 두 곳만 확인했습니다.
COMPLETE는 확인과 USB 저장 완료이며, 파일 존재나 UDS 사용을 보장하지 않습니다.
report.txt의 protocol_state와 protocol_state_files를 확인해 주세요.
캐시는 과거 선택값이며 현재 ECU 응답이나 플랩 제어 가능 여부가 아닙니다.
차량 진단 요청·MICOM 송신·캐시 생성·내부 저장소 변경은 하지 않았습니다.
결과 폴더는 프로젝트 private 아래 별도 폴더로 복사하고 공개하지 마세요.
PRIVATE
[ "$?" -eq 0 ] || exit 3
show_or_abort 99 "5/5 USB 저장 마무리" "쓰기 완료 확인 · 제한 60초 · 완료 알림까지 기다리세요."
progress_finish || exit 4
echo "Collection complete. Exhaust flap control is not implemented."
exit 0
