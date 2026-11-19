#!/system/bin/sh
# NEMESIS 1.16.7+ DialogActivity progress mode. No APK or service installation.
COLLECTOR_VERSION=${COLLECTOR_VERSION:-0.2.1}
PERCENT=0
COPIED=0
SKIPPED=0
UI_LOG=/dev/null
PROGRESS_STATE=RUNNING
STEP=준비
DETAIL="차량과 USB를 확인합니다"
OUT=

# Apply a timeout to each child, including ActivityManager, and reap it.
# A kernel-level USB I/O stall can still delay termination; never claim success.
# FAST commands can cost one polling interval; the percentage is work, not time.
run_bounded() {
    LIMIT=$1
    shift
    "$@" &
    CHILD_PID=$!
    WAITED=0
    while kill -0 "$CHILD_PID" 2>/dev/null; do
        if [ "$WAITED" -ge "$LIMIT" ]; then
            kill -TERM "$CHILD_PID" 2>/dev/null
            sleep 1
            kill -KILL "$CHILD_PID" 2>/dev/null
            wait "$CHILD_PID" 2>/dev/null
            CHILD_PID=
            return 124
        fi
        sleep 1
        WAITED=$((WAITED + 1))
    done
    wait "$CHILD_PID"
    COMMAND_RC=$?
    CHILD_PID=
    return "$COMMAND_RC"
}

progress_snapshot() {
    [ -n "$OUT" ] || return 0
    {
        echo "version=$COLLECTOR_VERSION"
        echo "state=$PROGRESS_STATE"
        echo "percent=$PERCENT"
        echo "percent_basis=completed_work_steps_not_bytes_or_time"
        echo "stage=$STEP"
        echo "current=$DETAIL"
        echo "copied=$COPIED"
        echo "missing_optional_or_required=$SKIPPED"
    } > "$OUT/progress.txt" || return 1
    echo "percent=$PERCENT state=$PROGRESS_STATE stage=$STEP current=$DETAIL copied=$COPIED missing=$SKIPPED" >> "$OUT/events.log"
}

progress_ui() {
    UI_MODE=$1
    UI_MESSAGE=$2
    run_bounded 5 am start -n com.nemesis.manager/.DialogActivity -f 0x34000000 \
        --es nemesis_mode "$UI_MODE" --es nemesis_message "$UI_MESSAGE" > "$UI_LOG" 2>&1 || return 1
    if [ "$UI_LOG" != /dev/null ] &&
       grep -E 'Error:|Exception|does not exist|Permission Denial' "$UI_LOG" >/dev/null 2>&1; then
        return 1
    fi
    return 0
}

progress_text() {
    BAR=
    CELL=0
    FILLED=$((PERCENT / 10))
    while [ "$CELL" -lt 10 ]; do
        if [ "$CELL" -lt "$FILLED" ]; then BAR="${BAR}#"; else BAR="${BAR}-"; fi
        CELL=$((CELL + 1))
    done
    MESSAGE="분석 파일 추출 v$COLLECTOR_VERSION · ${PERCENT}%
[$BAR] 작업 단계 기준
$STEP
$DETAIL
복사 $COPIED / 없음 $SKIPPED
완료 알림 전에는 USB를 빼지 마세요."
}

progress_show() {
    # Never go backwards, and never display 100 from an ordinary work update.
    NEXT_PERCENT=$1
    [ "$NEXT_PERCENT" -lt 100 ] || NEXT_PERCENT=99
    [ "$NEXT_PERCENT" -lt "$PERCENT" ] || PERCENT=$NEXT_PERCENT
    STEP=$2
    DETAIL=$3
    progress_snapshot || return 1
    progress_text
    progress_ui progress "$MESSAGE"
}

progress_failure() {
    PROGRESS_STATE=FAILED
    [ "$PERCENT" -lt 100 ] || PERCENT=99
    DETAIL=$1
    progress_snapshot
    # Best effort when the USB itself or ActivityManager failed.
    progress_ui result_fail "추출 중단 · ${PERCENT}%
$STEP
$DETAIL
생성된 결과 폴더를 보관해 주세요.
저장 완료가 확인되지 않았습니다."
}

show_or_abort() {
    if ! progress_show "$1" "$2" "$3"; then
        [ -z "$OUT" ] || echo "collection=FAILED_UI" >> "$OUT/report.txt"
        progress_failure "진행 화면 또는 USB 기록을 갱신할 수 없습니다."
        exit 5
    fi
}

progress_finish() {
    # Caller has verified mandatory inputs. These last writes must be flushed
    # BEFORE the native UI is permitted to display 100% and the script exits 0.
    PERCENT=100
    STEP="5/5 추출 완료"
    DETAIL="NEMESIS 완료 알림 후 USB를 분리하세요."
    PROGRESS_STATE=COMPLETE
    if ! progress_report_status COMPLETE || ! progress_snapshot || ! run_bounded 60 sync; then
        progress_report_status FAILED_SYNC
        progress_failure "USB 저장 마무리에 실패했습니다. 완료로 간주하지 마세요."
        return 1
    fi
    # No more writes to USB after the successful final sync.
    UI_LOG=/dev/null
    progress_ui progress "분석 파일 추출 v$COLLECTOR_VERSION · 100%
[##########] 작업 단계 완료
필수 파일 확인과 USB 저장 마무리 완료
복사 $COPIED / 없음 $SKIPPED
곧 NEMESIS 완료 알림이 표시됩니다."
    sleep 2
    return 0
}

progress_report_status() {
    # Keep the detailed report intact. A separate tiny terminal result avoids
    # rereading and replacing a report that was still READY_TO_SYNC on a car.
    echo "collection=$1" > "$OUT/result.txt"
}
