#!/system/bin/sh
# One shot; reads selected stock files, writes only beside this script on USB.
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
. "$USB_DIR/progress.sh"
PROFILE=full
STEMS="automotive framework framework2 services core ext android.policy"
PRIMARY_STEM=automotive
SLOT_COUNT=14
if [ "${1-}" = --services-only ]; then
    PROFILE=services
    STEMS=automotive-service
    PRIMARY_STEM=automotive-service
    SLOT_COUNT=2
fi
show_or_abort 0 "1/5 대상 확인" "차량 소프트웨어와 USB를 확인합니다."
trap 'if [ -n "$CHILD_PID" ]; then kill -TERM "$CHILD_PID" 2>/dev/null; sleep 1; kill -KILL "$CHILD_PID" 2>/dev/null; wait "$CHILD_PID" 2>/dev/null; fi; progress_failure "실행 중단 신호를 받았습니다."; exit 130' INT TERM HUP

PRODUCT=$(getprop ro.build.product) || exit 1
case "$PRODUCT" in
    CN7NPE.KOR.0000.V039.001.260902|CN7NPE.KOR.S5W_M.V039.001.260902) ;;
    *) progress_failure "CN7NPE 한국형 V039.001.260902만 지원합니다."; exit 2 ;;
esac
[ "$(getprop ro.board.platform)" = tcc803x ] || {
    progress_failure "TCC803x 헤드유닛만 지원합니다."
    exit 2
}

# mkdir is exclusive. Never overwrite a previous export or follow its symlink.
INDEX=1
OUT=
while [ "$INDEX" -le 20 ]; do
    CANDIDATE="$USB_DIR/CN7NPE-exhaust-private-$INDEX"
    if mkdir "$CANDIDATE" 2>/dev/null; then
        OUT=$CANDIDATE
        break
    fi
    INDEX=$((INDEX + 1))
done
[ -n "$OUT" ] || { progress_failure "USB 결과 폴더를 만들 수 없습니다."; exit 3; }
mkdir "$OUT/stock" || { progress_failure "USB 저장 공간을 확인해 주세요."; exit 3; }
UI_LOG="$OUT/ui.log"
exec 2> "$OUT/collector-errors.log"
show_or_abort 5 "1/5 대상 확인" "대상 확인 완료 · USB에 새 결과 폴더 생성"

REPORT="$OUT/report.txt"
ERRORS=0
FRAMEWORK=0
SERVICE_CODE=0
NMODE=0
{
    echo "CN7NPE exhaust research collector 0.2.1"
    echo "profile=$PROFILE"
    echo "flap_control=NOT_IMPLEMENTED"
    echo "product=$PRODUCT"
    echo "platform=tcc803x"
    echo "android=$(getprop ro.build.version.release)"
    echo "sdk=$(getprop ro.build.version.sdk)"
    echo "Stock files below are private analysis inputs, not redistributable assets."
} > "$REPORT" || exit 3

copy_stock() {
    SOURCE=$1
    DEST=$2
    [ -f "$SOURCE" ] && [ -r "$SOURCE" ] || return 1
    if run_bounded 60 cp "$SOURCE" "$OUT/stock/$DEST"; then
        echo "copied=$SOURCE -> stock/$DEST" >> "$REPORT" || exit 3
        COPIED=$((COPIED + 1))
        return 0
    fi
    echo "copy_failed=$SOURCE" >> "$REPORT" || exit 3
    ERRORS=$((ERRORS + 1))
    echo "collection=FAILED_COPY" >> "$REPORT"
    progress_failure "파일 복사 실패 또는 60초 시간 초과: $DEST"
    exit 4
}

# Paired JAR/ODEX and boot dependencies for off-car analysis. No /data, modem,
# logcat, contact database, VIN, settings database or full getprop collection.
CHECKED=0
show_or_abort 10 "2/5 프레임워크 수집" "$SLOT_COUNT개 후보 파일을 차례대로 확인합니다."
for STEM in $STEMS; do
    for EXT in jar odex; do
        SOURCE="/system/framework/$STEM.$EXT"
        show_or_abort $((10 + CHECKED * 60 / SLOT_COUNT)) "2/5 프레임워크 수집" "현재: $STEM.$EXT · 복사 제한 60초"
        if copy_stock "$SOURCE" "$STEM.$EXT"; then
            [ "$STEM" = "$PRIMARY_STEM" ] && FRAMEWORK=$((FRAMEWORK + 1))
            if [ "$STEM" = automotive-service ] && [ "$EXT" = odex ]; then SERVICE_CODE=1; fi
        else
            SKIPPED=$((SKIPPED + 1))
            echo "missing=$SOURCE" >> "$REPORT"
        fi
        CHECKED=$((CHECKED + 1))
    done
done
if [ "$PROFILE" = services ]; then
    for FRAMEWORK_PATH in /system/framework/*.jar /system/framework/*.odex; do
        [ -f "$FRAMEWORK_PATH" ] && echo "${FRAMEWORK_PATH##*/}" >> "$OUT/framework-files.txt"
    done
fi

# Enumerate only system packages; keep only N-mode package identifiers.
# Paths from PackageManager are data, never evaluated as shell code.
if [ "$PROFILE" = full ]; then
show_or_abort 70 "3/5 N 모드 앱 확인" "시스템 앱 목록을 확인합니다 · 제한 30초"
if run_bounded 30 pm list packages -s > "$OUT/system-packages.tmp" 2>/dev/null; then
    while IFS= read -r LINE; do
        PKG=${LINE#package:}
        case "$PKG" in
            com.hkmc.*nmode*|com.mobis.*nmode*)
                case "$PKG" in *[!a-zA-Z0-9._]*) continue ;; esac
                echo "$PKG" >> "$OUT/nmode-packages.txt" || exit 3
                ;;
        esac
    done < "$OUT/system-packages.tmp"
else
    echo "package_list_failed=yes" >> "$REPORT"
    ERRORS=$((ERRORS + 1))
    echo "collection=FAILED_PACKAGE_LIST" >> "$REPORT"
    progress_failure "앱 목록 확인 실패 또는 30초 시간 초과"
    exit 4
fi

if [ -f "$OUT/nmode-packages.txt" ]; then
    APP_INDEX=0
    while IFS= read -r PKG; do
        echo "nmode_package=$PKG" >> "$REPORT"
        show_or_abort 80 "3/5 N 모드 앱 확인" "앱 경로 확인 · 제한 30초"
        if ! run_bounded 30 pm path "$PKG" > "$OUT/package-paths.tmp" 2>/dev/null; then
            ERRORS=$((ERRORS + 1))
            echo "collection=FAILED_PACKAGE_PATH" >> "$REPORT"
            progress_failure "N 모드 앱 경로 확인 실패 또는 30초 시간 초과"
            exit 4
        fi
        while IFS= read -r LINE; do
            case "$LINE" in package:/system/*.apk) ;;
                *) continue ;;
            esac
            SOURCE=${LINE#package:}
            case "$SOURCE" in */../*|*/./*) continue ;; esac
            show_or_abort 85 "4/5 N 모드 앱 수집" "현재: nmode-$APP_INDEX.apk · 복사 제한 60초"
            if copy_stock "$SOURCE" "nmode-$APP_INDEX.apk"; then
                NMODE=$((NMODE + 1))
                show_or_abort 90 "4/5 N 모드 앱 수집" "현재: nmode-$APP_INDEX.odex · 복사 제한 60초"
                copy_stock "${SOURCE%.apk}.odex" "nmode-$APP_INDEX.odex" || SKIPPED=$((SKIPPED + 1))
            else
                SKIPPED=$((SKIPPED + 1))
            fi
            APP_INDEX=$((APP_INDEX + 1))
        done < "$OUT/package-paths.tmp"
    done < "$OUT/nmode-packages.txt"
fi
fi

# rm only our two temporary, newly created files; no recursive deletion.
show_or_abort 95 "5/5 결과 확인" "필수 파일과 복사 결과를 확인합니다."
rm -f "$OUT/system-packages.tmp" "$OUT/package-paths.tmp"
REQUIRED_OK=0
if [ "$FRAMEWORK" -gt 0 ] && [ "$ERRORS" -eq 0 ]; then
    if [ "$PROFILE" = services ]; then
        [ "$SERVICE_CODE" -eq 1 ] && REQUIRED_OK=1
    elif [ "$NMODE" -gt 0 ]; then
        REQUIRED_OK=1
    fi
fi
{
    echo "automotive_files=$FRAMEWORK"
    echo "primary_component=$PRIMARY_STEM"
    echo "nmode_apks=$NMODE"
    echo "copy_or_package_errors=$ERRORS"
    if [ "$REQUIRED_OK" -eq 1 ]; then
        echo "collection=READY_TO_SYNC"
    else
        echo "collection=INCOMPLETE"
    fi
} >> "$REPORT" || exit 3

cat > "$OUT/PRIVATE-README.txt" <<'PRIVATE'
배기 플랩 제어 기능은 아직 없습니다. 분석용 추출 파일입니다.
이 폴더를 PC에서 ZIP으로 압축해 개발 대화에 비공개로 첨부해 주세요.
stock/에는 제조사 APK/JAR/ODEX가 들어 있습니다.
공개 GitHub 저장소, 릴리스, 이슈에 올리지 마세요.
result.txt의 collection=COMPLETE는 추출 완료일 뿐 제어 성공이 아닙니다.
시스템 파일을 수정하거나 배기 플랩 명령을 보내지 않았습니다.
PRIVATE
[ "$?" -eq 0 ] || exit 3
echo "Saved: $OUT"
if [ "$REQUIRED_OK" -ne 1 ]; then
    echo "Some required inputs are missing. Keep the partial export for analysis."
    progress_failure "필수 파일이 누락되었습니다. 결과 폴더를 보관해 주세요."
    exit 4
fi
show_or_abort 99 "5/5 USB 저장 마무리" "저장 장치 쓰기 완료를 확인합니다 · 제한 60초"
progress_finish || exit 4
echo "Collection complete. Exhaust flap control is not implemented."
exit 0
